# Modos de operação e Domínio como referência

## Decisão de produto

O Domínio permanece como referência externa das notas. O Fiscal Checker organiza empresas e competências, analisa arquivos disponíveis e permite tratar as exceções. A direção futura é um fluxo de coleta e tratamento integrado com JettaX/ONVIO; a primeira etapa usa importação de CSVs exportados e adaptados ao contrato do protótipo.

Não há leitura ou escrita na API desses produtos nesta implementação. A origem “Domínio — exportação CSV” é uma declaração do operador, não uma confirmação de sincronização. O código da empresa no Domínio facilita localizar a referência, sem transmitir dados ao sistema externo.

## Manual

1. Cadastrar ou selecionar a empresa e a competência.
2. Importar notas em CSV ou XML compatível, com escrituração e valores informados para completar a análise; eventos e cadastros são complementos.
3. Consultar chaves, emissão, situação, valores, emitente, destinatário, repetições, origem e arquivos. Uma chave repetida ocupa uma linha no inventário, com a contagem de registros preservada; a análise continua identificando as duplicidades.
4. Baixar o inventário completo em CSV para conferência ou executar as verificações do protótipo sobre aquela versão ativa.
5. Corrigir os registros na origem. Uma nova exportação completa cria outra versão, sem apagar as evidências anteriores.

Cada importação é um retrato completo da competência. Não há edição direta ou exclusão de notas originais pela interface. Para complementar uma importação, enviar novamente o conjunto completo. A análise aceita documentos fora da competência para apontar essa divergência; documentos sem relação com o CNPJ selecionado são rejeitados.

O layout aceito está em `docs/caso-csv.md`, nos modelos para download e na lista de colunas da interface. Ainda é preciso validar um exemplo de CSV nativo do Domínio para implementar seu conversor. Selecionar uma origem não converte automaticamente os arquivos.

## Automático

O operador seleciona empresas e uma competência. O lote executa as verificações sobre a versão ativa de cada inventário, exibe o progresso e isola falhas por empresa. O processamento é sequencial nesta versão e depende do processo local do Streamlit; não é um serviço de agendamento nem uma fila de execução em segundo plano.

As situações são:

| Situação | Significado |
| --- | --- |
| Com divergências | Os insumos da análise local estão presentes, o processamento foi concluído e há ocorrências. |
| Sem divergências detectadas | As verificações executadas não encontraram ocorrências nos arquivos disponíveis. Não certifica regularidade fiscal nem completude da coleta. |
| Incompleta | Faltam arquivos, houve falha, a fonte mudou ou existe consulta externa pendente. |

Domínio, SEFAZ, Portal Nacional e prefeitura podem ser selecionados como consultas desejadas. São registrados na cobertura como **Pendente de integração**, sem simular coleta. O município/UF da empresa contextualiza a solicitação de prefeitura. JettaX/ONVIO permanecem integrações futuras; não há formulário de credenciais enquanto esses conectores não existem.

## Tratamento e relatórios

A fila permite filtrar por empresa, gravidade e tipo de divergência. Cada ocorrência expõe valores e evidências, recebe situação e anotação, e mantém histórico local. Resolver exige explicar o tratamento realizado na origem. Não há envio automático de mensagens ao cliente; a prévia pode ser editada e baixada.

O tratamento pertence à versão do inventário e à ocorrência. Reexecutar a mesma versão preserva as decisões; uma nova versão exige nova revisão. O resultado original da análise permanece imutável. O CSV de pendências exportado contém a situação atual do tratamento, enquanto o HTML técnico conserva as ocorrências detectadas naquela execução.

O pacote de análise contém resumo do lote, cobertura, erros, relatório HTML e resultado JSON por empresa, além do CSV consolidado de pendências. Os relatórios são gerados sob demanda. O inventário possui download próprio no modo manual.

## Armazenamento e limites

- SQLite guarda cadastro, referências de importação, resultados e decisões; não guarda outra cópia das notas normalizadas.
- Uploads são preservados uma vez em uma pasta com manifesto e SHA-256. Reimportar conteúdo idêntico da mesma empresa e competência reutiliza a versão. Os parâmetros de cálculo participam da identificação da versão.
- Casos já existentes podem ser vinculados sem copiar seus arquivos. A leitura verifica o conteúdo contra o manifesto e a versão registrada.
- Há uma versão ativa por empresa e competência. As anteriores continuam disponíveis e não são somadas ao inventário, evitando contagem duplicada entre exportações.
- Arquivos e resultados anteriores não são expurgados automaticamente. Uma política de retenção é uma etapa posterior.
- Sem autenticação, atribuição de responsável por usuário, integração com portais ou regras de apuração reais. As verificações atuais usam o perfil fictício do caso de demonstração.
