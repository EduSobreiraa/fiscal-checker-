# Fiscal Checker

Plataforma local para simular o fechamento mensal de uma empresa fictícia. A tela inicial oferece **Coletar notas fiscais** e **Importar notas locais**. A coleta ainda está em planejamento; a importação funcional usa **CSVs**, parâmetros tributários fictícios e uma interface simples em verde claro e branco. A análise gera divergências com evidências, memória de cálculo e relatórios para revisão humana.

## Usar pela interface

Uma pessoa responsável pela instalação executa uma vez:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./scripts/start-ui.sh
```

No Windows, no PowerShell, execute na pasta do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Depois, o usuário abre **http://127.0.0.1:8501** no mesmo computador. Na tela de boas-vindas, escolhe **Importar notas locais** para analisar o caso pronto ou enviar `nfe.csv`, `lancamentos.csv` e `valor_informado.csv`, com arquivos complementares opcionais. A interface oferece CSVs de exemplo para download. A opção **Coletar notas fiscais** apresenta a etapa futura de integração com fontes fiscais ou com o fluxo Jettax/ONVIO da empresa; ela ainda não executa coleta.

Os arquivos enviados e os relatórios ficam em uma pasta de dados do **usuário que executa a plataforma**, independente da localização do repositório: `~/.local/share/fiscal-checker/` no Linux, `~/Library/Application Support/Fiscal Checker/` no macOS ou `%LOCALAPPDATA%\Fiscal Checker\` no Windows. Dentro dela, a aplicação cria `casos/<nome-do-caso>/` e `relatorios/<nome-do-caso>/`. O usuário também pode baixar os resultados pela página.

Para instalar em outra máquina, basta copiar o projeto, instalar as dependências e iniciar a interface com o usuário que utilizará os dados. O responsável pela instalação pode configurar uma pasta base diferente com um **caminho absoluto**, por exemplo `FISCAL_DATA_ROOT=/dados/fiscal-checker ./scripts/start-ui.sh`. As configurações antigas `FISCAL_UPLOAD_ROOT` e `FISCAL_OUTPUT_ROOT` continuam disponíveis para definir as duas pastas separadamente. Uma pasta compartilhada entre usuários exige permissões de acesso adequadas; esta versão local ainda não tem contas nem separação de dados por usuário no navegador.

No Streamlit Community Cloud, aponte o arquivo principal para `app.py`. A configuração de rede da nuvem é usada automaticamente; o iniciador local continua limitado a `127.0.0.1`. O armazenamento local do Community Cloud não é persistente, e este protótipo ainda não separa dados entre visitantes. Use apenas dados sintéticos na implantação pública e baixe os resultados gerados.

## Caso de demonstração e avaliação

O [caso CSV](data/synthetic/case-2026-08-comercial-modelo-csv/README.md) contém seis documentos, um evento, escrituração e um gabarito de dez divergências. O relatório compara automaticamente as ocorrências encontradas com esse gabarito: previstas, detectadas, ausentes, extras e com fonte de evidência. O [guia dos CSVs](docs/caso-csv.md) explica os arquivos.

O cálculo sintético considera vendas de `2050.00`, devolução de `150.00`, base de `1900.00`, PIS/Pasep de `19.00` e Cofins de `38.00`. Essas taxas **não representam legislação fiscal**; o perfil está em `config/tax_profile.json` dentro do caso.

## Executar e testar pelo terminal

```bash
npm ci
npm run check:case -- data/synthetic/case-2026-08-comercial-modelo-csv
python3 -m unittest discover -s tests -v
npm test
python3 -m fiscal_engine --input data/synthetic/case-2026-08-comercial-modelo-csv --output output/case-csv --competencia 2026-08
```

A saída contém `normalized.json`, `calculation.json`, `result.json`, `occurrences.csv`, `triagem.csv`, `previa-cliente.txt` e `report.html`. A triagem agrupa divergências por documento; na interface, o analista pode selecionar vários grupos, revisar e editar a prévia de contato com o cliente. O Python também aceita a [fixture XML](data/synthetic/case-2026-08-comercial-modelo/README.md) de referência. O coletor SEFAZ em JavaScript continua separado do caso sintético; seus requisitos estão em [docs/coleta-sefaz.md](docs/coleta-sefaz.md).

O escopo e as etapas do analista estão em [especificacao_fiscal_checker.md](especificacao_fiscal_checker.md) e [docs/fluxo-de-fechamento.md](docs/fluxo-de-fechamento.md). O [mapa de fontes da Bahia e nacionais](docs/fontes-documentos-ba-nacional.md) registra os próximos documentos e portais a considerar. O [fluxo em lote com Jettax e ONVIO](docs/fluxo-jettax-onvio-lotes.md) descreve como reduzir o trabalho nota por nota na implantação. Nenhum arquivo real ou certificado é necessário para esta demonstração.
