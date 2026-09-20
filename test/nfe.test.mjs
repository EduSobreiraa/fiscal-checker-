import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { gzipSync } from 'node:zlib';
import { buildRequest, collectOnce, parseResponse } from '../src/nfe.mjs';

const document = '12345678000195';
const xmlDocument = '<resNFe xmlns="http://www.portalfiscal.inf.br/nfe"><chNFe>123</chNFe></resNFe>';

function soap({ status, lastNsu = '000000000000001', maxNsu = lastNsu, docs = [] }) {
  const zip = docs.map(({ nsu, schema = 'resNFe_v1.00.xsd' }) =>
    `<docZip NSU="${nsu}" schema="${schema}">${gzipSync(xmlDocument).toString('base64')}</docZip>`).join('');
  return `<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><nfeDistDFeInteresseResponse><nfeDistDFeInteresseResult><retDistDFeInt><tpAmb>2</tpAmb><cStat>${status}</cStat><xMotivo>teste</xMotivo><ultNSU>${lastNsu}</ultNSU><maxNSU>${maxNsu}</maxNSU><loteDistDFeInt>${zip}</loteDistDFeInt></retDistDFeInt></nfeDistDFeInteresseResult></nfeDistDFeInteresseResponse></soap:Body></soap:Envelope>`;
}

test('pedido usa ambiente, documento e cursor corretos', () => {
  const request = buildRequest({ document, environment: 'homologacao', nsu: 7 });
  assert.match(request, /<tpAmb>2<\/tpAmb>/);
  assert.match(request, /<CNPJ>12345678000195<\/CNPJ>/);
  assert.match(request, /<ultNSU>000000000000007<\/ultNSU>/);
});

test('salva lote e cursor; respeita intervalo sem fazer nova chamada', async (context) => {
  const dir = await fs.mkdtemp(path.join(tmpdir(), 'nfe-test-'));
  context.after(() => fs.rm(dir, { recursive: true, force: true }));
  const pfxPath = path.join(dir, 'fake.pfx');
  await fs.writeFile(pfxPath, 'fake');
  let calls = 0;
  const options = {
    document, environment: 'homologacao', pfxPath, passphrase: 'teste', dataDir: dir,
    now: () => Date.parse('2026-09-20T12:00:00Z'),
    transport: async () => {
      calls++;
      return soap({ status: '138', docs: [{ nsu: '000000000000001' }] });
    },
  };
  const first = await collectOnce(options);
  assert.equal(first.count, 1);
  assert.equal(first.lastNsu, '000000000000001');
  assert.equal(await fs.readFile(path.join(dir, 'homologacao', document, '000000000000001-resNFe_v1.00.xml'), 'utf8'), xmlDocument);
  assert.equal(JSON.parse(await fs.readFile(path.join(dir, 'homologacao', document, 'state.json'))).lastNsu, first.lastNsu);
  const second = await collectOnce(options);
  assert.equal(second.status, 'aguardando');
  assert.equal(calls, 1);
});

test('não avança cursor quando XML compactado é inválido', async (context) => {
  const dir = await fs.mkdtemp(path.join(tmpdir(), 'nfe-test-'));
  context.after(() => fs.rm(dir, { recursive: true, force: true }));
  const pfxPath = path.join(dir, 'fake.pfx');
  await fs.writeFile(pfxPath, 'fake');
  const bad = soap({ status: '138', docs: [{ nsu: '000000000000001' }] }).replace(/H4sI[A-Za-z0-9+/=]+/, 'invalid');
  await assert.rejects(() => collectOnce({ document, pfxPath, passphrase: 'teste', dataDir: dir, transport: async () => bad }));
  await assert.rejects(() => fs.readFile(path.join(dir, 'homologacao', document, 'state.json')), { code: 'ENOENT' });
});

test('interpreta resposta vazia', () => {
  const response = parseResponse(soap({ status: '137', lastNsu: '000000000000000', maxNsu: '000000000000000' }), 'homologacao');
  assert.equal(response.status, '137');
  assert.equal(response.documents.length, 0);
});
