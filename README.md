# Conferência de Apurações do Simples

Aplicação local para acelerar a conferência em lote de relatórios de apuração do Simples Nacional gerados pelo Domínio. O operador informa a pasta raiz de uma competência, e o sistema organiza as empresas em três grupos:

- **Sem exceções detectadas:** priorizadas para a revisão final e entrega pela equipe.
- **Fila de revisão:** divergências objetivas, com valores e relatórios de origem.
- **Erros de processamento:** relatórios que não permitiram uma análise confiável.

O sistema não recalcula tributos, não substitui o Domínio e não certifica que uma apuração está fiscalmente correta. “Sem exceções detectadas” descreve somente as regras executadas sobre os relatórios disponíveis.

## Interface

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./scripts/start-ui.sh
```

Abra http://127.0.0.1:8501, informe o diretório da competência e selecione **Analisar relatórios**.

A estrutura de entrada planejada é:

```text
/dados/dominio/2026-08/
  001_EMPRESA_A/
    simples_apuracao.pdf
    faturamento_simples.pdf
    resumo_acumuladores.pdf
```

Hoje, a interface aceita as fixtures JSON para demonstrar a análise completa. Os PDFs são identificados e catalogados por empresa e tipo de relatório, mas entram como erro de extração até que o adapter seja validado com amostras reais do Domínio.

## Linha de comando

```bash
npm run assess -- --input fixtures/dominio-batch/2026-08 --output output/simples-2026-08.json
```

O JSON de saída contém a competência, resumo, situação por empresa, findings, valores usados, fontes, hashes e avisos de extração.

## Testes

```bash
.venv/bin/python -m unittest discover -s tests -v
npm test
```

## Próxima etapa

Quando houver PDFs reais e autorizados, será implementado somente o `DominioPdfAssessmentExtractor`. O modelo normalizado, as regras, a classificação, o lote e a tela permanecem os mesmos. Veja o checklist em [DOMINIO_BATCH_ASSESSMENT.md](docs/DOMINIO_BATCH_ASSESSMENT.md).

O pipeline sintético anterior de NF-e foi preservado no código para referência e testes, mas não é exposto pela interface desta versão.
