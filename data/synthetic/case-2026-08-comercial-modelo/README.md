# Caso sintético de agosto de 2026

Esta pasta simula o pacote recebido pelo analista em 25/09/2026. Os CNPJs e as chaves servem somente para relacionar as fontes; as notas não são fiscalmente válidas. As alíquotas em `config/tax_profile.json` são **fictícias** e servem apenas para testar cálculos determinísticos.

- `raw/notas/`: seis XMLs de NF-e, incluindo uma cópia duplicada, e um evento de cancelamento.
- `raw/escrituracao/lancamentos.csv`: escrituração reduzida com divergências deliberadas.
- `raw/cadastros/`: cadastro fictício de produto e participantes.
- `raw/declaracoes/valor_informado.json`: valores informados para comparação posterior.
- `manifest.json`: arquivos brutos, tamanhos e hashes SHA-256.
- `expected_occurrences.json`: regras que a etapa de reconciliação deverá identificar.

O script `scripts/build_synthetic_case.py` recria esta fixture durante o desenvolvimento. O pipeline **somente lê** `raw/` e não deve executar o gerador em produção.
