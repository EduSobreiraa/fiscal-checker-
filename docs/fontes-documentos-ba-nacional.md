# Fontes de documentos fiscais: Bahia e serviços nacionais

Levantamento em **20/09/2026** para orientar a coleta de documentos de clientes de UFs diferentes. Este mapa descreve **onde o documento é emitido ou autorizado** e **como o Fiscal Checker poderia obtê-lo**. Um portal de emissão ou uma consulta pública por chave não implica acesso automatizado à carteira de documentos de uma empresa.

## Mapa inicial

| Documento | Portal ou autorizador relevante | Caminho de coleta para análise | Estado no projeto |
| --- | --- | --- | --- |
| **NF-e, modelo 55** | [SEFAZ-BA](https://www.sefaz.ba.gov.br/inspetoria-eletronica/icms/documentos-fiscais/nota-fiscal-eletronica/) para autorização na Bahia; [Ambiente Nacional da NF-e](https://www.nfe.fazenda.gov.br/portal/webservices.aspx?AspxAutoDetectCookieSupport=1) para distribuição | XMLs emitidos guardados pelo emissor/ERP; para documentos de interesse recebidos, `NFeDistribuicaoDFe` com certificado e cursor NSU. Eventos e resumos exigem tratamento próprio. | Coletor nacional mínimo em JavaScript, sem validação real por falta de A1; importação XML no caso sintético. |
| **NFC-e, modelo 65** | [SEFAZ-BA / SVRS](https://www.sefaz.ba.gov.br/inspetoria-eletronica/icms/documentos-fiscais/nota-fiscal-de-consumidor-eletronica/) para autorização; consulta pública estadual por chave | Para vendas do próprio cliente, exportação dos XMLs pelo sistema de ponto de venda/ERP. A página de serviços lista autorização, eventos e consulta por chave; **não foi identificado nela um serviço de distribuição em lote para o contribuinte**. | Sem conector nem parser específico. |
| **NFS-e de serviços** | [Emissor Público Nacional](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual) quando o município utiliza esse produto; ou sistema municipal próprio | [ADN para contribuintes](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual/manual-contribuintes-apis-adn-sistema-nacional-nfse.pdf) permite consultar documentos em que o contribuinte é prestador, tomador ou intermediário, por NSU, e eventos por chave, com certificado. Emissões também podem ser exportadas do sistema usado pelo cliente. Confirmar cobertura e operação no município. | Sem conector nem parser específico. |
| **NFS-e e NFTS de Salvador** | [Nota Salvador](https://www2.sefaz.salvador.ba.gov.br/servicos/carta-de-servicos/nota-salvador-emissao-de-nota-fiscal) | Portal disponibiliza relatórios de documentos emitidos/recebidos; [manuais municipais](https://nota.salvador.ba.gov.br/artigo_prestador.asp?conteudo=Manuais) incluem exportação e integração. Verificar se os documentos do cliente já estão no ADN e quais arquivos o portal permite exportar antes de criar integração municipal. | Sem conector. |
| **CT-e, modelo 57** | Para a Bahia, a [SVRS autoriza](https://www.cte.fazenda.gov.br/portal/webServices.aspx/listaConteudo.aspx?tipoConteudo=B7kL1rP5cbU%3D); o Ambiente Nacional distribui | `CTeDistribuicaoDFe` consta da relação nacional de serviços. XMLs próprios também podem vir do sistema da transportadora. Exige estudo do leiaute, papéis de acesso e teste com certificado. | Sem conector. |
| **MDF-e, modelo 58** | [SEFAZ-BA / SVRS](https://www.sefaz.ba.gov.br/inspetoria-eletronica/icms/documentos-fiscais/manifesto-de-documentos-fiscais-eletronicos/) | A relação da Bahia inclui `MDFeDistribuicaoDFe`. Também é possível importar XMLs guardados pelo sistema emissor. | Sem conector. |
| **NFA-e baiana, modelo 55** | [Sistema de emissão de nota avulsa da SEFAZ-BA](https://www.sefaz.ba.gov.br/carta-de-servicos/) | Tratar primeiro como fonte de **XML modelo 55**, se disponibilizado ao interessado. Validar acesso caso a caso: a nota avulsa pode usar identificação do órgão emissor, e a disponibilidade pela distribuição nacional não deve ser presumida. | Sem fluxo específico. |

A [SEFAZ-BA lista outros documentos](https://www.sefaz.ba.gov.br/inspetoria-eletronica/icms/), como NFCom, NF3e e BP-e. Eles entram no inventário por perfil de cliente, depois dos documentos acima.

## Decisões para a arquitetura

1. **Cadastrar cada estabelecimento e município.** Guardar CNPJ/CPF, UF, município, tipos de documento usados, sistema emissor, papel do cliente em cada documento (emitente, destinatário, tomador etc.) e fonte disponível. Uma empresa pode usar mais de um portal.
2. **Separar emissão de obtenção.** Serviços `NFeAutorizacao` e `NFeConsultaProtocolo` da Bahia servem a finalidades diferentes de `NFeDistribuicaoDFe` nacional. Para documentos emitidos pelo próprio cliente, obter o XML do sistema que os emitiu é o caminho inicial mais direto. A distribuição nacional da NF-e fornece documentos e eventos **de interesse**; não pressupor que devolverá o XML da própria NF-e emitida. [Nota técnica da distribuição](https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=U0LlsYVGBRU%3D).
3. **Manter um adaptador por família de documento.** Cada conector preserva XML original, origem, hash, data de coleta, CNPJ consultado, ambiente e cursor quando houver. O parser de NF-e atual não deve ser aplicado a NFC-e, CT-e, MDF-e ou NFS-e sem suporte explícito.
4. **Conservar o XML como evidência; gerar CSV só para análise.** O CSV facilita conferência e tratamento em Python, mas não substitui o arquivo fiscal original nem seus eventos. Registrar no manifesto a ligação entre XML, CSV derivado e versão do parser.
5. **Distinguir indisponibilidade de ausência de documento.** Falha de autenticação, município fora da cobertura testada, janela de distribuição e ausência de NSU não significam que não houve emissão. Exibir cobertura e pendências por fonte no relatório.

## Ordem sugerida de implementação

| Ordem | Entrega | Por quê |
| --- | --- | --- |
| 1 | Importador de XMLs próprios de NF-e e NFC-e, com detecção do modelo 55/65 e eventos | Funciona sem certificado no protótipo e cobre a operação de mercadorias e varejo sem consultar cada portal. |
| 2 | Integrar o coletor nacional de NF-e ao manifesto e à interface | Aproveita o código já existente, após obter A1 autorizado e testar a distribuição real. |
| 3 | Prova de conceito da API ADN NFS-e e importação de exportações de Salvador | A documentação atual prevê acesso do contribuinte por certificado; a cobertura municipal e a sequência de NSU precisam ser testadas com um cliente autorizado. |
| 4 | CT-e e MDF-e para clientes com transporte | Há serviços de distribuição, mas exigem modelos de dados e regras próprios. |

**Dependências reais:** autorização do cliente para acesso, certificado adequado quando o serviço exigir, amostras legítimas de cada tipo de documento e identificação do sistema emissor. Nenhum novo portal foi conectado ou testado com credenciais neste levantamento.

## Fontes oficiais consultadas

- [SEFAZ-BA: NF-e](https://www.sefaz.ba.gov.br/inspetoria-eletronica/icms/documentos-fiscais/nota-fiscal-eletronica/) e [NFC-e](https://www.sefaz.ba.gov.br/inspetoria-eletronica/icms/documentos-fiscais/nota-fiscal-de-consumidor-eletronica/).
- [Portal Nacional da NF-e: serviços web](https://www.nfe.fazenda.gov.br/portal/webservices.aspx?AspxAutoDetectCookieSupport=1) e [nota técnica da distribuição](https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=U0LlsYVGBRU%3D).
- [NFS-e Nacional: documentação atual](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual), [API do ADN para contribuintes](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual/manual-contribuintes-apis-adn-sistema-nacional-nfse.pdf) e [produtos escolhidos por município](https://www.gov.br/nfse/pt-br/municipios/produtos-disponiveis).
- [Salvador: Nota Salvador](https://www2.sefaz.salvador.ba.gov.br/servicos/carta-de-servicos/nota-salvador-emissao-de-nota-fiscal) e [manuais de integração/exportação](https://nota.salvador.ba.gov.br/artigo_prestador.asp?conteudo=Manuais).
- [Portal Nacional do CT-e: serviços web e UFs autorizadoras](https://www.cte.fazenda.gov.br/portal/webServices.aspx/listaConteudo.aspx?tipoConteudo=B7kL1rP5cbU%3D), [SEFAZ-BA: MDF-e](https://www.sefaz.ba.gov.br/inspetoria-eletronica/icms/documentos-fiscais/manifesto-de-documentos-fiscais-eletronicos/) e [SEFAZ-BA: carta de serviços/NFA-e](https://www.sefaz.ba.gov.br/carta-de-servicos/).
