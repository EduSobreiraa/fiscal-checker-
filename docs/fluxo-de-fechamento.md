# Fluxo do analista — fechamento mensal

Caso piloto: **Comercial Modelo Bahia Ltda.**, competência **agosto de 2026**, análise simulada em **25/09/2026**. Todos os dados são sintéticos. A data representa o cenário de trabalho, não um prazo legal configurado no software.

| Momento do trabalho | Pergunta do analista | Entrada | Registro produzido |
| --- | --- | --- | --- |
| 1. Recebimento | Recebi todas as fontes esperadas? | XML de NF-e, escrituração, cadastros, valor informado | `raw/` e `manifest.json` com hash e origem |
| 2. Triagem | Os arquivos são legíveis e da competência/empresa corretas? | Manifesto e arquivos brutos | Erros de ingestão e validação com caminho do arquivo |
| 3. Organização | Quais documentos e itens cada fonte descreve? | XML e escrituração reduzida | Documentos normalizados, preservando referência à origem |
| 4. Conciliação | O que consta em uma fonte e falta ou diverge na outra? | Documentos normalizados | Ocorrências com regra, valores e evidência |
| 5. Apuração simulada | Qual resultado decorre dos parâmetros aprovados para o caso? | Documentos conciliados e perfil tributário versionado | Memória de cálculo, valor calculado e diferença para o informado |
| 6. Revisão | O que exige decisão humana? | Ocorrências e memória de cálculo | Status de revisão e relatório HTML/JSON/CSV |

## Pastas e responsabilidade

```text
data/synthetic/case-2026-08-comercial-modelo/ Caso sintético completo versionado
  metadata.json                        Empresa, competência, data e fontes esperadas
  raw/notas/                           XMLs originais da simulação
  raw/escrituracao/                    Lançamentos sintéticos (EFD reduzida)
  raw/cadastros/                       Produtos e outros cadastros recebidos
  raw/declaracoes/                     Valor informado para comparação
  manifest.json                        Índice e SHA-256 de cada arquivo bruto
  expected_occurrences.json            Gabarito das divergências conhecidas

data/                                   Fixture sintética versionada; demais coletas fora do Git
output/                                 Resultados gerados; fora do Git
src/                                    Conector JS atual da SEFAZ, opcional no piloto
fiscal_engine/                          Futuro pipeline Python
```

O **caso de estudo** entra diretamente no pipeline Python. A origem dos arquivos pode ser `synthetic`, `local_import` ou um conector autorizado, mas o processamento posterior recebe o mesmo contrato: `metadata.json`, `manifest.json` e `raw/`. O conector da SEFAZ permanece separado do piloto; ele não é necessário para concluir este caso.

## Controle de passagem

Cada etapa só deve ser marcada como concluída quando seus insumos e evidências estiverem registrados. Arquivos em `raw/` não são modificados pelo pipeline. Correções na interpretação produzem novos dados tratados e ocorrências, preservando o arquivo recebido e seu hash. Um arquivo inválido entra na lista de erros; os demais continuam processáveis.

O perfil tributário fica em `config/tax_profile.json` dentro do caso. Ele explicita taxas e políticas **fictícias**; a memória de cálculo e o relatório são gerados em `output/`. O resultado permanece pendente de revisão humana.
