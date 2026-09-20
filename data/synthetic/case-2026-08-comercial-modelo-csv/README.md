# Caso de teste em CSV

Versão tabular do caso de agosto de 2026. Os seis arquivos em `raw/` são CSVs sintéticos; `manifest.json` traz tamanho e SHA-256 de cada um. Os arquivos em `config/` são parâmetros internos do teste e usam taxas **fictícias**.

O gabarito em `expected_occurrences.json` contém dez ocorrências. O motor deve calcular base de `1900.00`, PIS/Pasep `19.00` e Cofins `38.00`, e registrar as dez ocorrências com fonte de evidência. O relatório acrescenta uma avaliação automática contra esse gabarito.

Use `python3 -m fiscal_engine --input data/synthetic/case-2026-08-comercial-modelo-csv --output output/case-csv --competencia 2026-08` ou abra o caso pela interface local.

A pasta é gerada por `python3 -m scripts.build_csv_case`. A fixture XML original continua disponível apenas como referência para verificar que os dois formatos produzem o mesmo resultado.
