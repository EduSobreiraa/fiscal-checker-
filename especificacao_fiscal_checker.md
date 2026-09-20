# Fiscal Checker — Especificação do Caso de Estudo

## 1. Objetivo

Construir um protótipo que simule parte da atividade de um fiscal/analista contábil durante o fechamento mensal de uma empresa.

O primeiro caso de estudo será baseado em uma empresa fictícia, com dados sintéticos referentes à competência **agosto de 2026**. O sistema deverá receber documentos fiscais, tratar os dados, realizar uma apuração simulada de PIS/Pasep e Cofins, identificar inconsistências e gerar um relatório auditável.

O sistema é de apoio à análise. Ele não substitui a validação de um contador, não transmite declarações e não realiza pagamentos.

## 2. Escopo do primeiro caso

### Empresa fictícia

- Nome: `Comercial Modelo Bahia Ltda.`
- Atividade: comércio de eletrônicos
- Localização de referência: Bahia
- Regime tributário simulado: Lucro Presumido
- Competência: agosto de 2026
- Data de referência do caso: 25/09/2026
- Dados: totalmente sintéticos

O regime tributário, alíquotas, códigos de receita e exceções devem ficar em configuração externa. Não devem ser espalhados pelo código nem tratados como regras universais.

### Resultado esperado

O sistema deverá produzir:

1. Dados fiscais brutos preservados.
2. Dados normalizados.
3. Memória de cálculo da apuração.
4. Lista de divergências e evidências.
5. Resumo dos valores esperados.
6. Relatório HTML para leitura humana.
7. JSON estruturado para futuras integrações ou análise por LLM.
8. CSV com as ocorrências.

## 3. Arquitetura definida

O scraper existente em JavaScript será mantido como camada de coleta. O processamento fiscal será implementado em Python.

```text
Scraper JavaScript
        ↓
Arquivos brutos + manifest.json
        ↓
Parser e validador Python
        ↓
Normalização
        ↓
Apuração determinística
        ↓
Reconciliação e motor de regras
        ↓
Resultado estruturado
        ↓
Relatórios HTML, JSON e CSV
```

### Responsabilidades por tecnologia

#### JavaScript

- Interagir com navegadores e portais.
- Controlar sessão, autenticação e download quando autorizado.
- Processar páginas dinâmicas.
- Baixar arquivos sem alterar o conteúdo original.
- Gerar o manifesto dos arquivos coletados.

#### Python

- Ler XML, SPED e arquivos auxiliares.
- Validar esquemas e campos obrigatórios.
- Normalizar documentos.
- Realizar cálculos monetários.
- Aplicar regras fiscais.
- Reconciliar diferentes fontes.
- Gerar resultados e relatórios.
- Executar testes automatizados.

O scraper não deve conter regras fiscais. O motor Python também não deve depender da forma como os arquivos foram coletados.

## 4. Contrato entre o scraper e o pipeline Python

O scraper deverá gravar os dados em uma estrutura semelhante a:

```text
data/
├── raw/
│   ├── notas/
│   ├── sped/
│   └── exportacoes/
├── manifest.json
└── metadata.json
```

### Exemplo de `manifest.json`

```json
{
  "case_id": "case-2026-08-comercial-modelo",
  "company_id": "empresa-ficticia-001",
  "competencia": "2026-08",
  "collected_at": "2026-09-20T12:00:00Z",
  "source": "synthetic",
  "files": [
    {
      "path": "raw/notas/nfe_000001.xml",
      "type": "nfe_xml",
      "sha256": "hash-do-arquivo",
      "size_bytes": 12345
    }
  ]
}
```

### Regras do contrato

- Arquivos brutos são somente leitura após a coleta.
- Cada arquivo deve possuir hash SHA-256.
- O pipeline deve registrar a origem do arquivo.
- O pipeline deve ser executável mesmo sem o scraper, usando uma pasta local.
- Arquivos inválidos devem gerar erro rastreável, sem interromper desnecessariamente todo o lote.
- Nenhum arquivo original deve ser sobrescrito.

## 5. Entradas do primeiro caso

O conjunto sintético deverá conter:

- XMLs de NF-e emitidas em agosto de 2026.
- XMLs de NF-e canceladas.
- XMLs de devolução, quando aplicável.
- Registro ou resumo equivalente à escrituração fiscal.
- Relação de produtos.
- Cadastro de emitentes e destinatários.
- Parâmetros tributários da empresa.
- Valor declarado ou esperado para comparação.

Para a primeira versão, o SPED pode ser representado por um arquivo sintético reduzido, desde que conserve a relação entre documentos, itens, valores e impostos. A implementação deve permitir substituir esse arquivo por um EFD real posteriormente.

## 6. Modelo de dados normalizado

O processamento deve converter fontes diferentes para modelos internos estáveis.

### Documento fiscal

```json
{
  "document_id": "nfe-000001",
  "access_key": "chave-da-nfe",
  "document_type": "NFE",
  "issue_date": "2026-08-05",
  "status": "authorized",
  "issuer_tax_id": "identificador-ficticio",
  "recipient_tax_id": "identificador-ficticio",
  "total_value": "1250.00",
  "icms_base": "1250.00",
  "icms_value": "225.00",
  "items": []
}
```

### Item fiscal

```json
{
  "document_id": "nfe-000001",
  "line_number": 1,
  "product_code": "PROD-001",
  "description": "Produto de teste",
  "ncm": "00000000",
  "cfop": "5102",
  "cst": "000",
  "quantity": "1.0000",
  "unit_value": "1250.00",
  "total_value": "1250.00",
  "pis_value": "0.00",
  "cofins_value": "0.00"
}
```

### Ocorrência

```json
{
  "occurrence_id": "occ-000001",
  "rule_id": "DOC_MISSING_IN_SPED",
  "severity": "high",
  "status": "pending_review",
  "document_id": "nfe-000001",
  "message": "Documento fiscal encontrado no XML, mas não localizado na escrituração.",
  "evidence": {
    "xml_path": "raw/notas/nfe_000001.xml",
    "source_record": null,
    "access_key": "chave-da-nfe"
  },
  "expected_value": "1250.00",
  "declared_value": null
}
```

Valores monetários devem ser tratados com `Decimal`, nunca com `float`.

## 7. Pipeline de processamento

### Etapa 1 — Ingestão

- Ler `manifest.json`.
- Confirmar a competência.
- Confirmar a empresa do caso.
- Validar a existência dos arquivos.
- Calcular ou conferir os hashes.
- Registrar erros de leitura.

### Etapa 2 — Parsing

- Ler XMLs com parser seguro.
- Extrair cabeçalho, situação, participantes, itens e tributos.
- Ler os registros do arquivo de escrituração.
- Preservar o número da linha ou identificador de origem.

### Etapa 3 — Normalização

- Padronizar datas.
- Padronizar identificadores.
- Converter valores para `Decimal`.
- Normalizar códigos fiscais.
- Uniformizar estados, municípios e unidades.
- Criar identificadores internos estáveis.

### Etapa 4 — Validação

Validar:

- Estrutura mínima do XML.
- Presença da chave do documento.
- Data dentro da competência.
- Valores numéricos válidos.
- Soma dos itens contra o total do documento.
- Campos obrigatórios.
- Documentos cancelados e autorizados.

### Etapa 5 — Apuração

Calcular, de forma configurável:

- Receita bruta elegível.
- Exclusão de documentos cancelados.
- Tratamento de devoluções.
- Tratamento de descontos, quando aplicável.
- Base de cálculo.
- PIS/Pasep esperado.
- Cofins esperada.
- Valor declarado ou informado pelo caso.
- Diferença entre valor esperado e declarado.

As alíquotas e regras devem vir de `config/tax_profile.json`.

### Etapa 6 — Reconciliação

Comparar:

- XML contra escrituração.
- XML contra resumo de apuração.
- Escrituração contra apuração calculada.
- Apuração calculada contra valor declarado.

O resultado deve apontar a origem exata da diferença.

### Etapa 7 — Motor de regras

O motor deve ser determinístico, testável e independente do scraper.

Regras iniciais:

| ID | Regra | Severidade sugerida |
|---|---|---|
| `DOC_MISSING_IN_SPED` | NF-e existente no XML, mas ausente na escrituração | Alta |
| `DOC_WITHOUT_XML` | Registro na escrituração sem XML correspondente | Alta |
| `VALUE_MISMATCH` | Valor do XML diferente do valor escriturado | Alta |
| `TAX_BASE_MISMATCH` | Base de cálculo divergente | Alta |
| `TAX_VALUE_MISMATCH` | Valor do tributo divergente | Alta |
| `CANCELLED_INCLUDED` | Documento cancelado incluído na apuração | Crítica |
| `RETURN_NOT_DEDUCTED` | Devolução não deduzida da receita elegível | Alta |
| `DUPLICATE_DOCUMENT` | Documento ou chave duplicada | Alta |
| `INVALID_PERIOD` | Documento fora da competência analisada | Média |
| `ITEM_TOTAL_MISMATCH` | Soma dos itens diferente do total da nota | Média |
| `MISSING_REQUIRED_FIELD` | Campo obrigatório ausente | Média |
| `RATE_CONFIGURATION_MISSING` | Parâmetro tributário ausente | Crítica |

Cada regra deve retornar:

- ID da regra.
- Mensagem explicativa.
- Severidade.
- Documento afetado.
- Evidência.
- Valor esperado.
- Valor encontrado.
- Origem dos dados.
- Status de revisão.

## 8. Relatório

### Relatório HTML

O relatório deve conter:

1. Identificação do caso.
2. Empresa e competência.
3. Fontes analisadas.
4. Quantidade de documentos processados.
5. Resumo da apuração.
6. Total de ocorrências por severidade.
7. Tabela detalhada de divergências.
8. Evidências e caminhos dos arquivos.
9. Memória de cálculo.
10. Limitações do processamento.
11. Conclusão: pendente de revisão humana.

### Arquivo JSON

O JSON deve conter o resultado completo e servir como contrato para futuras integrações ou análise por LLM.

### Arquivo CSV

O CSV deve ser orientado à revisão humana, com pelo menos:

```text
occurrence_id,rule_id,severity,status,document_id,access_key,message,expected_value,declared_value,source_path
```

## 9. Estrutura sugerida do projeto

```text
fiscal-checker/
├── scraper-js/
├── fiscal_engine/
│   ├── __init__.py
│   ├── cli.py
│   ├── config/
│   ├── models/
│   ├── parsers/
│   ├── validators/
│   ├── normalization/
│   ├── calculations/
│   ├── reconciliation/
│   ├── rules/
│   └── reports/
├── config/
│   ├── company_profile.json
│   └── tax_profile.json
├── data/
│   ├── raw/
│   ├── normalized/
│   └── synthetic/
├── output/
├── tests/
│   ├── fixtures/
│   ├── test_parsers.py
│   ├── test_calculations.py
│   ├── test_reconciliation.py
│   └── test_rules.py
├── requirements.txt
└── README.md
```

## 10. Execução esperada

```bash
python -m fiscal_engine \
  --input ./data \
  --config ./config \
  --output ./output \
  --competencia 2026-08
```

Saídas esperadas:

```text
output/
├── result.json
├── occurrences.csv
├── calculation.json
└── report.html
```

## 11. Testes obrigatórios

Criar fixtures sintéticas para os seguintes cenários:

1. Todos os documentos conciliados.
2. NF-e ausente na escrituração.
3. Registro sem XML.
4. Divergência de valor.
5. Divergência de base de cálculo.
6. Documento cancelado incluído.
7. Documento duplicado.
8. Documento fora da competência.
9. Soma dos itens diferente do total.
10. Parâmetro tributário ausente.

Cada teste deve verificar não apenas se a regra foi acionada, mas também se a evidência correta foi incluída no resultado.

## 12. Segurança e rastreabilidade

- Não utilizar dados fiscais reais no repositório.
- Não armazenar certificados digitais no projeto.
- Não tentar acessar portais sem autorização.
- Não contornar CAPTCHA, autenticação ou controles de acesso.
- Não enviar dados para APIs externas no MVP.
- Não alterar o SPED ou os XMLs originais.
- Registrar hashes dos arquivos.
- Separar dados brutos, tratados e resultados.
- Redigir o relatório como análise auxiliar, não como decisão fiscal definitiva.

## 13. Fora do escopo inicial

- Transmissão de declarações.
- Pagamento de impostos.
- Alteração automática do SPED.
- Consulta a empresas reais.
- Uso obrigatório de certificado digital.
- Integração inicial com Domínio, Jettax ou ONVIO.
- Uso de LLM para decidir se uma ocorrência é válida.
- Scraping de portais não autorizados.

## 14. Critérios de aceite

O caso de estudo será considerado concluído quando:

- O scraper JavaScript gerar arquivos e manifesto válidos.
- O Python processar os mesmos arquivos diretamente a partir da pasta local.
- Os dados brutos permanecerem intactos.
- A apuração for reproduzível.
- As regras identificarem todos os erros previamente inseridos.
- Cada ocorrência possuir evidência rastreável.
- O relatório HTML for compreensível para um analista contábil.
- O JSON puder ser consumido por outro componente.
- Os testes automatizados passarem.
- Nenhum dado real ou credencial for necessário.

## 15. Ordem de implementação

1. Inspecionar o scraper JavaScript existente.
2. Definir e documentar o formato real do `manifest.json`.
3. Criar os dados sintéticos da empresa fictícia.
4. Implementar modelos e parsing.
5. Implementar normalização.
6. Implementar apuração com `Decimal`.
7. Implementar reconciliação.
8. Implementar as regras iniciais.
9. Criar testes com divergências conhecidas.
10. Gerar JSON, CSV e HTML.
11. Validar o caso completo ponta a ponta.
12. Documentar limitações e próximos conectores.

## 15.1. Fixture sintética implementada

O primeiro conjunto de dados foi criado em:

```text
data/synthetic/case-2026-08-comercial-modelo/
```

Ele contém:

- perfil da empresa fictícia;
- perfil tributário configurável;
- XMLs sintéticos de vendas, cancelamento, devolução e documento fora da competência;
- escrituração sintética em formato delimitado;
- apuração declarada deliberadamente divergente;
- resultado esperado das regras;
- hashes SHA-256 no manifesto;
- instruções de execução e premissas do caso.

As divergências conhecidas são mantidas em `expected_occurrences.json` para que os testes possam comparar o resultado real do motor com o resultado esperado.

## 15.2. Caso tabular e interface local

O primeiro fluxo para usuários comuns usa a versão tabular em `data/synthetic/case-2026-08-comercial-modelo-csv/`. Os documentos, eventos, escrituração, cadastros e valores informados de entrada são CSVs. A fixture XML anterior permanece como referência de equivalência; o pipeline Python aceita ambas.

Uma interface local em Streamlit recebe os CSVs, salva cada caso em `data/inbox/<nome-do-caso>/`, gera metadados e manifesto com hashes, executa o motor e oferece os relatórios para download. A pasta base é configurável por `FISCAL_UPLOAD_ROOT`. O perfil tributário da interface é explicitamente fictício. O guia de formatos e uso está em `docs/caso-csv.md`.

O relatório do caso sintético compara as ocorrências encontradas com `expected_occurrences.json` e apresenta previstas, detectadas, ausentes, extras e com fonte de evidência. Casos enviados sem gabarito recebem o relatório de análise, sem pontuação do teste.

## 16. Orientação para o Codex

Implemente este projeto de forma incremental. Antes de alterar o scraper, inspecione os arquivos existentes e preserve seu comportamento funcional.

Priorize código simples, modular, testável e rastreável. Não implemente integrações reais, transmissão fiscal ou LLM nesta etapa.

O primeiro objetivo é provar que o sistema consegue receber dados sintéticos, realizar a apuração da competência agosto de 2026, detectar divergências conhecidas e gerar um relatório que um analista consiga revisar.

## 17. Referências oficiais do caso

- [Agenda Tributária da Receita Federal — setembro de 2026](https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2026/Setembro)
- [Vencimentos de 25/09/2026 — PIS/Pasep, Cofins e IPI](https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2026/Setembro/dia-25-09-2026)
- [Vencimentos de 30/09/2026 — IRPJ, CSLL e demais obrigações](https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2026/Setembro/dia-30-09-2026)
- [Programa validador da EFD ICMS/IPI](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/download/sped/efdi)

Essas referências servem para contextualizar o estudo de caso. O software não deve tratar o calendário ou a legislação como código fixo: prazos, regras e parâmetros devem ser versionados e atualizáveis.
