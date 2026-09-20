import { collectOnce } from './nfe.mjs';

try {
  const result = await collectOnce({
    document: process.env.NFE_DOCUMENTO,
    environment: process.env.NFE_AMBIENTE || 'homologacao',
    pfxPath: process.env.PFX_PATH,
    passphrase: process.env.PFX_PASSWORD,
    dataDir: process.env.NFE_DATA_DIR || 'data',
  });
  console.log(JSON.stringify(result, null, 2));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
