# Como usar o caso de teste CSV

O caso de demonstração está em [`data/synthetic/case-2026-08-comercial-modelo-csv/`](../data/synthetic/case-2026-08-comercial-modelo-csv/). Ele simula um fechamento mensal, com divergências conhecidas para medir se a ferramenta as encontrou. Todos os identificadores e parâmetros tributários são fictícios.

## Arquivos de entrada

| Arquivo | Obrigatório na interface | Conteúdo |
| --- | --- | --- |
| `nfe.csv` | Sim | Uma linha por item de NF-e. `document_ref` agrupa os itens da mesma nota; `access_key` relaciona nota, evento e escrituração. |
| `lancamentos.csv` | Sim | Escrituração reduzida: chave, registro de origem, total, bases e valores simulados de PIS/Cofins, inclusão na receita e abatimento de devolução. |
| `valor_informado.csv` | Sim | Uma linha com competência e valores informados de PIS/Pasep e Cofins. |
| `eventos.csv` | Não | Eventos associados a uma chave; no exemplo, o cancelamento. |
| `produtos.csv` | Não | Cadastro de produtos. |
| `participantes.csv` | Não | Cadastro de participantes. |

Os cabeçalhos exatos estão nos arquivos de exemplo. Não altere o nome das colunas. Valores monetários usam ponto decimal e são tratados com `Decimal`; booleanos usam `true` ou `false`.

## O que acontece após o envio

1. A interface salva os arquivos em `casos/<nome-do-caso>/raw/` dentro da pasta de dados do usuário que executa a aplicação (ou na pasta configurada pelo responsável pela instalação).
2. Gera `metadata.json` e `manifest.json` com hash SHA-256 de cada arquivo.
3. O Python confere a integridade, normaliza as fontes, calcula segundo o perfil sintético e identifica divergências.
4. O usuário vê o resumo e baixa o pacote com HTML, JSON e CSV. Os arquivos originais não são alterados.

O caso de demonstração contém um gabarito de dez ocorrências. Seu relatório informa quantas foram detectadas, quantas ficaram ausentes, quantas não eram esperadas e quantas têm fonte de evidência. Casos enviados sem gabarito recebem o relatório analítico, sem pontuação de teste.

## Limites desta versão

A interface é local, acessível em `http://127.0.0.1:8501` no computador em que foi iniciada. O navegador envia os arquivos para **esse computador**; ele não pode escolher livremente uma pasta do servidor. Por padrão, a pasta base pertence ao usuário que executa a aplicação. O responsável pela instalação pode alterá-la com `FISCAL_DATA_ROOT` ou `FISCAL_UPLOAD_ROOT`, sempre com caminho absoluto; cada caso recebe uma subpasta definida na tela. Esta versão não distingue usuários diferentes conectados ao mesmo processo no navegador.

O perfil disponível na interface usa apenas taxas fictícias. A ferramenta não transmite declarações nem substitui revisão contábil.
