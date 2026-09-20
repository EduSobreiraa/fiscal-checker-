# Coleta de NF-e de mercadorias

## Primeiro coletor

O repositório contém um coletor mínimo para **NF-e modelo 55** via `NFeDistribuicaoDFe`. Cada execução consulta um lote por `distNSU`, descompacta os XMLs recebidos e grava o cursor em `data/<ambiente>/<CPF-ou-CNPJ>/state.json`. Ele não manifesta notas em nome do destinatário nem consulta chaves individualmente.

Requisitos: Node.js 24+, certificado digital A1 `.pfx`/`.p12` do interessado e sua senha. Ainda não há certificado neste projeto, então a comunicação real com a SEFAZ não foi validada. O modo de homologação é o padrão; use produção para obter notas reais.

```bash
npm ci
export NFE_DOCUMENTO="SEU_CNPJ_COM_14_DIGITOS"
export PFX_PATH="/caminho/fora/do/repositorio/certificado.pfx"
read -rsp 'Senha do certificado: ' PFX_PASSWORD; echo
export PFX_PASSWORD
export NFE_AMBIENTE=producao
npm run collect
unset PFX_PASSWORD
```

Uma execução busca **um lote**. Se o resultado indicar `lastNsu` menor que `maxNsu`, execute novamente para buscar o próximo. Ao atingir o fim, o coletor grava um intervalo mínimo de uma hora antes da próxima consulta. O diretório `data/` é ignorado pelo Git, mas contém dados fiscais sensíveis: mantenha acesso restrito e faça backup seguro do cursor junto aos XMLs. Evite outra aplicação de distribuição usando o mesmo CNPJ sem compartilhar o cursor.

O arquivo `.lock` impede duas execuções simultâneas para o mesmo documento. Após uma interrupção abrupta, confirme que não há coleta em execução antes de remover esse arquivo para retomar.

## Caminho recomendado

Para **NF-e de mercadorias (modelo 55)** em que o titular do certificado participe da operação, usar o serviço oficial **NFeDistribuicaoDFe**. O serviço distribui documentos por NSU (Número Sequencial Único) mediante certificado digital do interessado. Isso fornece XML estruturado para a futura análise, sem depender da interface da consulta pública.

Fluxo proposto para a primeira implementação:

1. Receber o certificado digital e o CNPJ/CPF do interessado por configuração segura.
2. Consultar `distNSU` com o último `ultNSU` persistido (inicialmente zero).
3. Salvar os documentos e resumos retornados, identificando cada arquivo por NSU e esquema; atualizar o cursor somente depois de salvar o lote.
4. Repetir a partir do `ultNSU` retornado. Quando não houver documentos (`cStat=137`, ou `ultNSU=maxNSU`), aguardar pelo menos uma hora antes de consultar novamente.
5. Tratar resumos, XML completos e eventos como tipos diferentes. O XML completo de uma NF-e destinada ao interessado pode depender da manifestação do destinatário; essa manifestação tem efeitos fiscais e não deve ser feita automaticamente apenas para obter dados.

**Limites:** o serviço não é um catálogo público de todas as notas. O interessado precisa ter um papel contemplado pelas regras de distribuição. O emitente pode receber eventos de terceiros relativos às próprias notas, mas não deve contar com esse serviço para recuperar o XML que ele mesmo emitiu; esse XML deve vir do seu emissor/ERP. A consulta inicial só alcança os documentos disponíveis na janela de distribuição, descrita na documentação como os últimos três meses; para histórico anterior, será preciso importar XMLs existentes ou obtê-los do emissor. Várias aplicações consultando o mesmo CNPJ devem compartilhar o mesmo cursor de NSU para não provocar bloqueio por consumo indevido.

## Se o alvo for outro tipo de documento

| Tipo/fonte | Forma de obtenção | Dependência principal |
| --- | --- | --- |
| NFS-e de serviços no Sistema Nacional | API de distribuição do Ambiente de Dados Nacional (ADN), por NSU | Certificado do prestador, tomador ou intermediário; cobertura do sistema nacional |
| NFS-e em portal municipal fora do fluxo nacional | Integração própria do município ou arquivos fornecidos pelo contribuinte | Município e provedor usados |
| XML/PDF já disponíveis | Importação de arquivos | Acesso aos arquivos; PDF pode perder detalhes estruturados |
| Consulta pública por chave | Consulta pontual no portal | Chave de acesso e interação com CAPTCHA; inadequada para coleta contínua |

## Integração com o caso sintético

O conector ainda não produz o `manifest.json` exigido pelo caso de estudo. Essa adaptação pertence a uma etapa posterior; o piloto atual lê diretamente os arquivos sintéticos em `data/synthetic/`.

O [mapa de fontes da Bahia e nacionais](fontes-documentos-ba-nacional.md) orienta as próximas integrações.

## Fontes oficiais

- [Manual de Orientação do Contribuinte — NFeDistribuicaoDFe](https://moc.sped.fazenda.pr.gov.br/NFeDistribuicaoDFe.html)
- [Nota Técnica 2014.002 — distribuição de DF-e](https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=pem6jrh73h4%3D)
- [Relação de serviços web da NF-e](https://www.nfe.fazenda.gov.br/portal/webservices.aspx?AspxAutoDetectCookieSupport=1)
- [Aviso da NF-e sobre uso indevido e intervalos de consulta](https://www.nfe.fazenda.gov.br/portal/informe.aspx?AspxAutoDetectCookieSupport=1&ehCTG=false&page=7&pagesize=30)
- [Manual de APIs do ADN para contribuintes (NFS-e)](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual/manual-contribuintes-apis-adn-sistema-nacional-nfse.pdf)
