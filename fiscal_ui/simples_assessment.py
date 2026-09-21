"""Tela única da conferência por exceção de apurações do Simples."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from fiscal_engine.assessment.service import assess_batch


def _company_rows(companies: list[dict]) -> list[dict]:
    return [
        {
            "Empresa": item["company"]["name"],
            "CNPJ": item["company"].get("document") or "—",
            "Motivos": "; ".join(finding["code"] for finding in item["findings"]) or "Nenhuma exceção detectada",
        }
        for item in companies
    ]


def _details(companies: list[dict]) -> None:
    for item in companies:
        with st.expander(item["company"]["name"]):
            for finding in item["findings"]:
                st.markdown(f"**{finding['code']}** — {finding['message']}")
                if finding["expected"] is not None or finding["actual"] is not None:
                    st.write({"Esperado": finding["expected"], "Encontrado": finding["actual"], "Fontes": finding["sources"]})
            st.caption("Dados e relatórios usados na análise")
            st.json({
                "sources": item["assessment"]["sources"],
                "source_values": item["assessment"]["source_values"],
                "warnings": item["assessment"]["extraction"]["warnings"],
            })


def simples_assessment_page(fixtures: Path) -> None:
    st.title("Conferência rápida de apurações do Simples")
    st.write("Informe a pasta raiz da competência. O sistema localiza os relatórios de cada empresa, extrai os dados disponíveis e separa o que não teve exceções detectadas do que precisa de revisão.")
    st.info("A ferramenta confere consistência entre relatórios; ela não recalcula nem certifica a apuração tributária.")

    with st.form("assessment_input"):
        path_value = st.text_input(
            "Diretório raiz da competência",
            value=str(fixtures),
            help="Ex.: /dados/dominio/2026-08. Cada empresa deve ficar em sua própria subpasta.",
        )
        st.caption("Estrutura esperada: `2026-08/001_EMPRESA/simples_apuracao.pdf`, `faturamento_simples.pdf` e `resumo_acumuladores.pdf`.")
        submitted = st.form_submit_button("Analisar relatórios", type="primary")
    if submitted:
        try:
            st.session_state["simples_batch"] = assess_batch(Path(path_value))
            st.session_state["simples_path"] = path_value
        except (OSError, ValueError, TypeError) as exc:
            st.error(f"Não foi possível analisar a pasta: {exc}")
            return

    result = st.session_state.get("simples_batch")
    if not result:
        st.caption("Use as fixtures preenchidas para experimentar o fluxo. PDFs são catalogados, mas aguardam o adapter validado com amostras reais do Domínio.")
        return

    summary = result["summary"]
    st.subheader(f"Competência {result['period']}")
    a, b, c, d = st.columns(4)
    a.metric("Empresas processadas", summary["total"])
    b.metric("Sem exceções detectadas", summary["withoutExceptions"])
    c.metric("Para revisar", summary["review"])
    d.metric("Erro de processamento", summary["errors"])

    ready = [item for item in result["companies"] if item["status"] == "SEM_EXCECOES"]
    review = [item for item in result["companies"] if item["status"] == "REVISAR"]
    errors = [item for item in result["companies"] if item["status"] == "ERRO"]

    st.subheader("Sem exceções detectadas · priorizar entrega")
    st.caption("Estes relatórios não tiveram exceções nas regras executadas. A decisão de entrega continua sendo da equipe responsável.")
    st.dataframe(_company_rows(ready), hide_index=True, width="stretch")

    st.subheader("Fila de revisão")
    if review:
        st.dataframe(_company_rows(review), hide_index=True, width="stretch")
        _details(review)
    else:
        st.caption("Nenhuma empresa entrou na fila de revisão.")

    st.subheader("Erros de processamento")
    if errors:
        st.dataframe(_company_rows(errors), hide_index=True, width="stretch")
        _details(errors)
    else:
        st.caption("Nenhum erro de processamento.")

    st.download_button(
        "Baixar resultado estruturado JSON",
        json.dumps(result, ensure_ascii=False, indent=2),
        file_name=f"simples-{result['period']}.json",
        mime="application/json",
    )
