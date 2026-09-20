import { createHash, randomUUID } from 'node:crypto';
import { promises as fs } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import https from 'node:https';
import path from 'node:path';
import { XMLParser } from 'fast-xml-parser';

const HOUR_MS = 60 * 60 * 1000;
const SERVICE_NS = 'http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe';
const ENDPOINTS = {
  producao: 'https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx',
  homologacao: 'https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx',
};

function validNsu(value) {
  const nsu = String(value);
  if (!/^\d{1,15}$/.test(nsu)) throw new Error('NSU inválido');
  return nsu.padStart(15, '0');
}

export function buildRequest({ document, environment, nsu }) {
  const id = String(document);
  if (!/^(\d{11}|\d{14})$/.test(id)) throw new Error('Informe CPF (11 dígitos) ou CNPJ (14 dígitos)');
  if (!(environment in ENDPOINTS)) throw new Error('Ambiente inválido');
  const field = id.length === 14 ? 'CNPJ' : 'CPF';
  const tpAmb = environment === 'producao' ? '1' : '2';
  return `<?xml version="1.0" encoding="UTF-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><nfeDistDFeInteresse xmlns="${SERVICE_NS}"><nfeDadosMsg><distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01"><tpAmb>${tpAmb}</tpAmb><${field}>${id}</${field}><distNSU><ultNSU>${validNsu(nsu)}</ultNSU></distNSU></distDFeInt></nfeDadosMsg></nfeDistDFeInteresse></soap:Body></soap:Envelope>`;
}

const parser = new XMLParser({
  ignoreAttributes: false,
  removeNSPrefix: true,
  parseTagValue: false,
  processEntities: false,
  trimValues: true,
});

export function parseResponse(xml, environment) {
  if (Buffer.byteLength(xml) > 12 * 1024 * 1024) throw new Error('Resposta SOAP muito grande');
  if (/<!DOCTYPE|<!ENTITY/i.test(xml)) throw new Error('DTD não permitido na resposta');
  const body = parser.parse(xml)?.Envelope?.Body;
  if (body?.Fault) throw new Error(`Falha SOAP: ${JSON.stringify(body.Fault).slice(0, 500)}`);
  const result = body?.nfeDistDFeInteresseResponse?.nfeDistDFeInteresseResult?.retDistDFeInt;
  if (!result) throw new Error('Resposta SEFAZ sem retDistDFeInt');
  const status = String(result.cStat ?? '');
  const expectedEnvironment = environment === 'producao' ? '1' : '2';
  if (String(result.tpAmb) !== expectedEnvironment) throw new Error('Ambiente da resposta não corresponde à consulta');
  const docs = result.loteDistDFeInt?.docZip;
  const entries = docs === undefined ? [] : Array.isArray(docs) ? docs : [docs];
  if (entries.length > 50) throw new Error('Lote com mais de 50 documentos');
  return {
    status,
    reason: String(result.xMotivo ?? ''),
    lastNsu: result.ultNSU === undefined ? null : validNsu(result.ultNSU),
    maxNsu: result.maxNSU === undefined ? null : validNsu(result.maxNSU),
    documents: entries.map((entry) => {
      const nsu = validNsu(entry['@_NSU']);
      const schema = String(entry['@_schema'] ?? '');
      if (!/^[A-Za-z0-9_.-]+\.xsd$/.test(schema)) throw new Error('Schema de documento inválido');
      const content = gunzipSync(Buffer.from(String(entry['#text'] ?? ''), 'base64'), { maxOutputLength: 10 * 1024 * 1024 });
      if (!content.toString('utf8').trimStart().startsWith('<')) throw new Error('Documento não contém XML');
      return { nsu, schema, content };
    }),
  };
}

export function postSoap(url, body, pfx, passphrase) {
  return new Promise((resolve, reject) => {
    const request = https.request(new URL(url), {
      method: 'POST', pfx, passphrase, minVersion: 'TLSv1.2', timeout: 30_000,
      headers: {
        'Content-Type': 'text/xml; charset=utf-8',
        SOAPAction: `"${SERVICE_NS}/nfeDistDFeInteresse"`,
        'Content-Length': Buffer.byteLength(body),
      },
    }, (response) => {
      const chunks = [];
      let bytes = 0;
      response.on('data', (chunk) => {
        bytes += chunk.length;
        if (bytes > 12 * 1024 * 1024) return request.destroy(new Error('Resposta HTTP muito grande'));
        chunks.push(chunk);
      });
      response.on('end', () => {
        const xml = Buffer.concat(chunks).toString('utf8');
        if (response.statusCode !== 200) reject(new Error(`HTTP ${response.statusCode}: ${xml.slice(0, 500)}`));
        else resolve(xml);
      });
      response.on('error', reject);
    });
    request.on('timeout', () => request.destroy(new Error('Tempo de consulta esgotado')));
    request.on('error', reject);
    request.end(body);
  });
}

async function readState(file) {
  try {
    const state = JSON.parse(await fs.readFile(file, 'utf8'));
    state.lastNsu = validNsu(state.lastNsu);
    return state;
  } catch (error) {
    if (error.code === 'ENOENT') return { lastNsu: validNsu(0), nextAllowedAt: null };
    throw error;
  }
}

async function saveState(file, state) {
  const temporary = `${file}.${process.pid}.tmp`;
  try {
    await fs.writeFile(temporary, JSON.stringify(state, null, 2) + '\n', { mode: 0o600 });
    await fs.rename(temporary, file);
  } catch (error) {
    await fs.rm(temporary, { force: true });
    throw error;
  }
}

async function saveDocuments(directory, documents) {
  for (const document of documents) {
    const filename = path.join(directory, `${document.nsu}-${document.schema.slice(0, -4)}.xml`);
    const temporary = `${filename}.${randomUUID()}.tmp`;
    try {
      await fs.writeFile(temporary, document.content, { flag: 'wx', mode: 0o600 });
      await fs.link(temporary, filename);
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
      const existing = await fs.readFile(filename);
      const hash = (value) => createHash('sha256').update(value).digest('hex');
      if (hash(existing) !== hash(document.content)) throw new Error(`Documento existente diverge: ${filename}`);
    } finally {
      await fs.rm(temporary, { force: true });
    }
  }
}

export async function collectOnce({ document, environment = 'homologacao', pfxPath, passphrase, dataDir = 'data', transport = postSoap, now = () => Date.now() }) {
  buildRequest({ document, environment, nsu: 0 });
  if (!pfxPath) throw new Error('Informe PFX_PATH');
  if (!passphrase) throw new Error('Informe PFX_PASSWORD');
  const base = path.resolve(dataDir, environment, document);
  await fs.mkdir(base, { recursive: true, mode: 0o700 });
  const lock = path.join(base, '.lock');
  const handle = await fs.open(lock, 'wx', 0o600).catch((error) => {
    if (error.code === 'EEXIST') throw new Error('Já existe uma coleta em andamento para este documento');
    throw error;
  });
  try {
    const stateFile = path.join(base, 'state.json');
    const state = await readState(stateFile);
    if (state.nextAllowedAt && now() < Date.parse(state.nextAllowedAt)) {
      return { status: 'aguardando', nextAllowedAt: state.nextAllowedAt, lastNsu: state.lastNsu, count: 0 };
    }
    const request = buildRequest({ document, environment, nsu: state.lastNsu });
    const pfx = await fs.readFile(pfxPath);
    const response = parseResponse(await transport(ENDPOINTS[environment], request, pfx, passphrase), environment);
    if (response.status === '656') {
      const nextAllowedAt = new Date(now() + HOUR_MS).toISOString();
      await saveState(stateFile, { ...state, nextAllowedAt });
      throw new Error(`SEFAZ: 656 ${response.reason}. Nova tentativa após ${nextAllowedAt}`);
    }
    if (!['137', '138'].includes(response.status)) throw new Error(`SEFAZ: ${response.status} ${response.reason}`);
    if (!response.lastNsu || !response.maxNsu) throw new Error('Resposta sem cursores NSU');
    if (BigInt(response.lastNsu) < BigInt(state.lastNsu)) throw new Error('Resposta retrocedeu o cursor NSU');
    if (response.status === '137' && response.documents.length) throw new Error('Resposta 137 com documentos');
    if (response.status === '138' && !response.documents.length) throw new Error('Resposta 138 sem documentos');
    await saveDocuments(base, response.documents);
    const nextAllowedAt = response.status === '137' || response.lastNsu === response.maxNsu
      ? new Date(now() + HOUR_MS).toISOString() : null;
    await saveState(stateFile, { lastNsu: response.lastNsu, nextAllowedAt });
    return { status: response.status, lastNsu: response.lastNsu, maxNsu: response.maxNsu, nextAllowedAt, count: response.documents.length };
  } finally {
    await handle.close();
    await fs.rm(lock, { force: true });
  }
}
