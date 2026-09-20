import { createHash } from 'node:crypto';
import { promises as fs } from 'node:fs';
import path from 'node:path';

const caseDir = path.resolve(process.argv[2] || 'data/synthetic/case-2026-08-comercial-modelo-csv');

async function filesUnder(directory) {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const results = [];
  for (const entry of entries) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) results.push(...await filesUnder(absolute));
    else if (entry.isFile()) results.push(path.relative(caseDir, absolute).split(path.sep).join('/'));
    else throw new Error(`Entrada não suportada em raw/: ${absolute}`);
  }
  return results;
}

try {
  const metadata = JSON.parse(await fs.readFile(path.join(caseDir, 'metadata.json'), 'utf8'));
  const manifest = JSON.parse(await fs.readFile(path.join(caseDir, 'manifest.json'), 'utf8'));
  for (const field of ['case_id', 'company_id', 'competencia', 'source']) {
    if (!metadata[field] || manifest[field] !== metadata[field]) throw new Error(`Metadados divergentes: ${field}`);
  }
  if (!Array.isArray(manifest.files) || !manifest.files.length) throw new Error('Manifesto sem arquivos');
  const listed = new Set();
  const types = new Set();
  for (const file of manifest.files) {
    if (!/^raw\/(?:[A-Za-z0-9_.-]+\/)*[A-Za-z0-9_.-]+$/.test(file.path) || file.path.split('/').includes('..')) {
      throw new Error(`Caminho inválido no manifesto: ${file.path}`);
    }
    if (listed.has(file.path)) throw new Error(`Arquivo duplicado no manifesto: ${file.path}`);
    listed.add(file.path);
    types.add(file.type);
    const absolute = path.join(caseDir, file.path);
    const stat = await fs.lstat(absolute);
    if (!stat.isFile()) throw new Error(`Não é um arquivo regular: ${file.path}`);
    const bytes = await fs.readFile(absolute);
    const sha256 = createHash('sha256').update(bytes).digest('hex');
    if (stat.size !== file.size_bytes || sha256 !== file.sha256) throw new Error(`Tamanho ou hash divergente: ${file.path}`);
  }
  for (const expected of metadata.expected_sources) {
    if (!types.has(expected)) throw new Error(`Fonte esperada ausente: ${expected}`);
  }
  const actual = await filesUnder(path.join(caseDir, 'raw'));
  for (const file of actual) if (!listed.has(file)) throw new Error(`Arquivo bruto fora do manifesto: ${file}`);
  console.log(`Caso íntegro: ${manifest.case_id} (${listed.size} arquivos).`);
} catch (error) {
  console.error(`Caso inválido: ${error.message}`);
  process.exitCode = 1;
}
