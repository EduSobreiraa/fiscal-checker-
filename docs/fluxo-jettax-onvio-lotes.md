# Fluxo em lote com Jettax e ONVIO

Estudo em **20/09/2026**. Objetivo: reduzir a manipulação de notas individuais no fechamento de clientes da Bahia e de outras UFs, aproveitando a captura e a escrituração que o escritório já utiliza.

## Primeiro: identificar qual produto recebe as notas

**ONVIO Escrita** e **ERP Domínio com ONVIO Gestão** aparecem em rotinas diferentes. A equipe deve indicar em qual tela faz hoje o trabalho por nota, porque as possibilidades de lote mudam:

| Rotina existente | Recurso já documentado | Como testar sem desenvolvimento |
| --- | --- | --- |
| Jettax → **ERP Domínio** | A [integração Jettax–Domínio](https://www.jettax.com.br/blog/como-habilitar-a-integracao-com-o-erp-dominio/) permite envio automático ou processamento manual por **tipo, competência e empresas**. O Domínio importa pelo menu `Utilitários > Importação > Importação Padrão > Importação API` ou pelo painel `Docs Fiscais`. | Verificar módulo contratado, habilitar um cliente piloto, selecionar uma competência e comparar enviados, importados e pendentes. |
| Arquivos → **ONVIO Escrita** | O [suporte do ONVIO Escrita](https://suporte.dominioatendimento.com/central/faces/solucao-onvio.html?codigo=10041) descreve importação de NFS-e tomados/prestados em `xml`, `zip`, `7z` e `txt`, com opção de importar somente registros inexistentes e histórico de importação. | Exportar um lote de teste da Jettax, importar um arquivo compactado no ONVIO e verificar o histórico e as rejeições. A fonte confirma esse procedimento **para NFS-e**, não para todo tipo de documento. |
| Jettax → arquivos | A [Jettax divulga download de NF-e em lote](https://blog.jettax.com.br/produtos/jettax-nfe), com filtros por período e XML/PDF. | Exportar um mês de um cliente e conferir conteúdo, estrutura de pastas, eventos e contagens antes de usar o lote no Fiscal Checker. |

A [API da Thomson Reuters](https://developerportal.thomsonreuters.com/onvio-br-accounting-api/documents/documentao-api) documenta layouts de importação de NF-e, NFC-e, CT-e e NFS-e e um [recurso para criar lote](https://developerportal.thomsonreuters.com/onvio-br-accounting-api/swagger_openapi_document/invoiceintegrationresource/7807/100). Isso demonstra uma rota de integração técnica, mas acesso, credenciais, permissões, contratos e resposta real precisam ser confirmados antes de desenvolver um conector. **Não presumir que essa API permita ler ou exportar de volta todos os documentos já tratados no ONVIO.**

## Papel proposto para o Fiscal Checker

1. O operador seleciona **cliente, CNPJ, competência e tipo** e envia **um ZIP por lote** ou escolhe uma pasta de exportação administrada pelo escritório.
2. O sistema inventaria os XMLs e eventos, confirma o modelo do documento, CNPJ e competência, calcula SHA-256 e elimina duplicatas por chave + tipo de evento. Arquivos inválidos ficam em uma lista de pendências com motivo em português.
3. O lote original permanece como evidência. Os dados normalizados são exportados em CSV para análise Python, mantendo no manifesto a relação com o XML de origem.
4. O analista vê uma **fila de exceções**, agrupada por empresa e competência: nota ausente, cancelada, duplicada, sem escrituração, valor divergente ou tipo ainda não suportado. Os documentos regulares avançam juntos para a rotina de importação já usada pelo escritório.
5. O relatório compara **capturados pela Jettax**, **entregues ao ONVIO/Domínio**, **importados/escriturados** e **pendentes**. Uma nota só é marcada como concluída após confirmação do destino, não apenas por estar no ZIP.

O protótipo agora possui cadastro de empresas, inventário por competência e versão, importação manual de CSVs e XMLs compatíveis, análise de múltiplas empresas e fila persistente de tratamento. O Domínio é a referência externa; por ora, arquivos exportados devem seguir o modelo CSV documentado. O [fluxo implementado](modos-de-operacao.md) detalha a cobertura, o armazenamento sem cópias do inventário por execução e os limites. **A entrada ZIP, outros modelos fiscais, o conversor do CSV nativo do Domínio e a integração direta com JettaX/ONVIO ainda precisam ser implementados**.

## Cuidados que mudam o resultado do lote

- O [tutorial da Jettax](https://www.jettax.com.br/blog/como-habilitar-a-integracao-com-o-erp-dominio/) informa que o envio automático leva XMLs originais, sem as correções feitas na plataforma; o processamento manual permite selecionar correções. O escritório precisa definir qual versão usa na análise e na escrituração.
- O mesmo tutorial informa que a integração automática começa na data de ativação e que documentos anteriores exigem outro tratamento. Também informa que notas disponíveis via API têm uma janela de importação. Para histórico, planejar exportação/importação de arquivos e conferir a regra vigente no produto.
- Eventos de cancelamento devem acompanhar a nota. A [Jettax relata](https://www.jettax.com.br/blog/como-habilitar-a-integracao-com-o-erp-dominio/) que a situação pode aparecer regular no Domínio quando o evento não foi importado.
- Cada cliente pode usar fontes e municípios diferentes. Separar lotes por CNPJ, competência e documento evita atribuir nota ao cliente errado. Preservar a resposta e o histórico de importação do destino para auditoria.

## Piloto recomendado

Escolher **um cliente autorizado e uma competência já fechada**, com amostras de: ZIP exportado da Jettax, relatório de quantidade por tipo, histórico de importação do ONVIO/Domínio e escrituração resultante. Repetir o fluxo atual e medir:

| Indicador | Medida |
| --- | --- |
| Tempo de operação | Minutos gastos por competência e por 100 notas |
| Cobertura | Capturadas, entregues, importadas, escrituradas e pendentes |
| Qualidade | Duplicatas, cancelamentos sem evento, documentos rejeitados e diferenças de valor |
| Retrabalho | Quantidade de notas abertas individualmente e motivo |

**Etapa manual confirmada:** os funcionários conferem divergências para levá-las ao cliente. A primeira entrega técnica é a fila agrupada por documento e a prévia editável para contato, já disponíveis no caso sintético. Para conectar dados reais, obter um exemplo de exportação **sem dados sensíveis**, ou anonimizado, com a estrutura de arquivos preservada, e um exemplo do histórico de importação. A importação de ZIP e uma eventual integração por API dependem de validar o que os produtos já oferecem.
