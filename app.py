"""Interface local para montar casos CSV e revisar o resultado."""

from __future__ import annotations

import json
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st

from fiscal_engine.case_io import create_uploaded_case
from fiscal_engine.presentation import RULE_LABELS, SEVERITY_LABELS, STATUS_LABELS, user_error
from fiscal_engine.service import run_case
from fiscal_engine.storage import storage_paths
from fiscal_engine.triage import client_brief_text


ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "data/synthetic/case-2026-08-comercial-modelo-csv"
DATA_ROOT, UPLOAD_ROOT, OUTPUT_ROOT = storage_paths()
PROFILE = DEMO / "config/tax_profile.json"
st.session_state.setdefault("page", "home")

st.set_page_config(page_title="Fiscal Checker", page_icon="🟢", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.block-container {max-width: 1160px; padding-top: 2rem; padding-bottom: 4rem;}
.hero {background:#E9F8ED;border:1px solid #D4EBD9;border-radius:20px;padding:2.2rem 2.4rem;box-shadow:0 12px 32px rgba(36,103,61,.09);margin-bottom:1.3rem;}
.hero .eyebrow {color:#347A54;font-size:.76rem;font-weight:800;letter-spacing:.15em;text-transform:uppercase;margin:0 0 .65rem;}
.hero h1 {color:#173A29;font-size:2.4rem;line-height:1.15;letter-spacing:-.04em;margin:0 0 .6rem;}
.hero p {color:#42654D;font-size:1.02rem;margin:0;max-width:720px;}
.section-label {color:#347A54;font-size:.76rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase;margin:1.7rem 0 .3rem;}
.path-pill {background:#FFFFFF;border:1px solid #DCEDE0;border-radius:10px;padding:.75rem;color:#24533A;font: .78rem/1.45 ui-monospace,monospace;overflow-wrap:anywhere;box-shadow:0 4px 12px rgba(30,92,52,.04);}
div[data-testid="stVerticalBlockBorderWrapper"] {box-shadow:0 7px 22px rgba(30,92,52,.055);}
div[data-testid="stMetric"] {background:#F1F9F3;border:1px solid #DCEDE0;border-radius:14px;padding:1rem 1.15rem;box-shadow:0 5px 14px rgba(30,92,52,.04);}
.choice-card {min-height:150px;padding:.4rem .2rem;}
.choice-card h3 {color:#173A29;margin:0 0 .5rem;font-size:1.3rem;}
.choice-card p {color:#42654D;margin:0;line-height:1.55;}
</style>
""", unsafe_allow_html=True)

if st.session_state.page == "home":
    st.markdown("""
    <div class="hero"><p class="eyebrow">Fiscal Checker · análise assistida</p>
    <h1>Bem-vindo ao Fiscal Checker.</h1>
    <p>Escolha como deseja começar a reunir os documentos fiscais. Depois, a plataforma organiza as divergências para revisão da equipe.</p></div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="hero"><p class="eyebrow">Fiscal Checker · análise assistida</p>
    <h1>Documentos organizados. Revisão mais simples.</h1>
    <p>Reúna os arquivos, confira as divergências por documento e prepare os pontos que precisam ser levados ao cliente.</p></div>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Sua área de trabalho")
    st.caption("Os casos enviados são salvos nesta pasta do computador que executa a plataforma:")
    st.markdown(f'<div class="path-pill">{escape(str(UPLOAD_ROOT))}</div>', unsafe_allow_html=True)
    st.caption("Por padrão, cada usuário do sistema tem sua própria pasta de dados. O responsável pela instalação pode definir `FISCAL_DATA_ROOT`.")
    st.divider()
    st.markdown("**Fluxo**")
    st.markdown("1. Reunir documentos\n2. Conferir integridade\n3. Analisar divergências\n4. Preparar a revisão com o cliente")
    st.divider()
    st.caption("Uso local · dados permanecem neste computador · sem envio a APIs externas")

if st.session_state.page == "home":
    st.markdown('<p class="section-label">Como deseja começar?</p>', unsafe_allow_html=True)
    collect, local = st.columns(2, gap="large")
    with collect:
        with st.container(border=True):
            st.markdown('<div class="choice-card"><h3>Coletar notas fiscais</h3><p>Preparar uma coleta por fontes fiscais ou pelas integrações já usadas pela empresa, como Jettax e ONVIO/Domínio.</p></div>', unsafe_allow_html=True)
            st.button("Ver opção de coleta", key="open_collect", width="stretch",
                      on_click=lambda: st.session_state.update(page="collect"))
    with local:
        with st.container(border=True):
            st.markdown('<div class="choice-card"><h3>Importar notas locais</h3><p>Começar com arquivos disponíveis no computador e revisar as divergências por documento. Nesta versão, a entrada usa CSVs.</p></div>', unsafe_allow_html=True)
            st.button("Importar arquivos locais", type="primary", key="open_local", width="stretch",
                      on_click=lambda: st.session_state.update(page="local"))
    st.stop()

st.button("← Voltar ao início", key="back_home", on_click=lambda: st.session_state.update(page="home"))

if st.session_state.page == "collect":
    st.markdown('<p class="section-label">Coleta de documentos</p>', unsafe_allow_html=True)
    st.subheader("Coleta automática em planejamento")
    st.write("Este caminho será desenvolvido quando definirmos a fonte de coleta. Podemos usar serviços fiscais autorizados ou aproveitar as importações que a empresa já faz na Jettax e no ONVIO/Domínio.")
    st.info("A coleta ainda não está conectada à interface. O coletor experimental de NF-e existe no projeto, mas não foi validado com certificado A1 nem integrado ao fluxo de análise.")
    st.stop()

st.markdown('<p class="section-label">Importação local</p>', unsafe_allow_html=True)
st.caption("A importação funcional desta versão recebe CSVs. A entrada direta de XML ou ZIP de notas fiscais será adicionada em uma etapa posterior.")
demo_tab, upload_tab = st.tabs(["Explorar caso de teste", "Criar caso com CSVs"])

with demo_tab:
    st.markdown('<p class="section-label">Demonstração</p>', unsafe_allow_html=True)
    st.subheader("Um fechamento pronto para analisar")
    st.write("O caso fictício de agosto de 2026 contém vendas, cancelamento, devolução e divergências inseridas de propósito. Execute a análise para ver o relatório e comparar as ocorrências com o gabarito.")
    if st.button("Analisar caso de teste", type="primary", key="demo_run"):
        st.session_state.pop("last_result", None)
        st.session_state.pop("last_output", None)
        try:
            with st.spinner("Conferindo documentos e calculando resultados..."):
                result = run_case(DEMO, OUTPUT_ROOT / DEMO.name, "2026-08")
            st.session_state["last_result"] = result
            st.session_state["last_output"] = str(OUTPUT_ROOT / DEMO.name)
            st.success("Caso de teste analisado. Os resultados estão abaixo.")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            st.error(f"Não foi possível analisar o caso: {user_error(exc)}")

with upload_tab:
    st.markdown('<p class="section-label">Novo caso</p>', unsafe_allow_html=True)
    st.subheader("Envie os documentos em CSV")
    st.caption("O nome dos arquivos no seu computador não altera o destino. A plataforma os organiza nas pastas do caso e cria o manifesto automaticamente.")
    template = BytesIO()
    with ZipFile(template, "w", ZIP_DEFLATED) as zipped:
        for sample in sorted((DEMO / "raw").rglob("*.csv")):
            zipped.write(sample, arcname=sample.relative_to(DEMO / "raw"))
    st.download_button("Baixar CSVs de exemplo", template.getvalue(), file_name="exemplo-fiscal-checker-csv.zip", mime="application/zip", on_click="ignore")
    with st.form("new_case", clear_on_submit=False):
        left, right = st.columns(2)
        with left:
            case_id = st.text_input("Nome da pasta do caso", value="meu-caso-2026-08", help="Use letras minúsculas, números e hífens.")
            company_name = st.text_input("Nome da empresa fictícia", value="Comercial Modelo Bahia Ltda.")
            company_id = st.text_input("Identificador da empresa", value="empresa-ficticia-001")
        with right:
            tax_id = st.text_input("CNPJ fictício usado nos CSVs", value="99999999000199")
            competencia = st.text_input("Competência (AAAA-MM)", value="2026-08")
            reference_date = st.date_input("Data da análise", value=date.today())
        st.markdown("**Arquivos obrigatórios**")
        notes = st.file_uploader("NF-e e itens — nfe.csv", type="csv", max_upload_size=10, key="notes")
        bookkeeping = st.file_uploader("Escrituração — lancamentos.csv", type="csv", max_upload_size=10, key="bookkeeping")
        declared = st.file_uploader("Valores informados — valor_informado.csv", type="csv", max_upload_size=10, key="declared")
        with st.expander("Arquivos complementares"):
            events = st.file_uploader("Eventos — eventos.csv", type="csv", max_upload_size=10, key="events")
            products = st.file_uploader("Produtos — produtos.csv", type="csv", max_upload_size=10, key="products")
            participants = st.file_uploader("Participantes — participantes.csv", type="csv", max_upload_size=10, key="participants")
        st.info("A apuração nesta versão usa apenas o perfil **fictício** do caso de teste. O relatório é uma análise auxiliar para revisão humana.")
        submitted = st.form_submit_button("Salvar e analisar", type="primary")
    if submitted:
        st.session_state.pop("last_result", None)
        st.session_state.pop("last_output", None)
        selected = {
            "nfe_csv": notes, "escrituracao_reduzida_csv": bookkeeping,
            "valor_informado_csv": declared, "nfe_event_csv": events,
            "produtos_csv": products, "participantes_csv": participants,
        }
        uploads = {kind: upload.getvalue() for kind, upload in selected.items() if upload is not None}
        case_dir = None
        try:
            with st.spinner("Salvando e analisando o caso..."):
                case_dir = create_uploaded_case(
                    UPLOAD_ROOT, case_id=case_id, company_id=company_id,
                    company_name=company_name, company_tax_id=tax_id,
                    competencia=competencia, reference_date=reference_date,
                    uploads=uploads, synthetic_profile=PROFILE,
                )
                output_dir = OUTPUT_ROOT / case_id
                result = run_case(case_dir, output_dir, competencia)
            st.session_state["last_result"] = result
            st.session_state["last_output"] = str(output_dir)
            st.success(f"Caso salvo em {case_dir}. A análise está abaixo.")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            if case_dir is None:
                st.error(f"Não foi possível salvar o caso: {user_error(exc)}")
            else:
                st.error(f"O caso foi salvo em {case_dir}, mas a análise falhou: {user_error(exc)}")

if "last_result" in st.session_state:
    result = st.session_state["last_result"]
    output = Path(st.session_state["last_output"])
    summary = result["summary"]
    calc = result["calculation"]
    st.markdown('<p class="section-label">Resultado da análise</p>', unsafe_allow_html=True)
    st.subheader(result["company_name"])
    st.caption(f"Competência {result['competencia']} · {result['case_id']} · processamento {STATUS_LABELS.get(result['status'], result['status'])}")
    one, two, three, four = st.columns(4)
    one.metric("Documentos", summary["documents"])
    two.metric("Ocorrências", summary["occurrences"])
    three.metric("Base simulada", calc["eligible_revenue"])
    four.metric("Erros de entrada", summary["input_errors"])
    if result.get("evaluation"):
        evaluation = result["evaluation"]
        if evaluation["passed"]:
            st.success(f"Avaliação do caso de teste: {evaluation['matched']} de {evaluation['expected']} ocorrências esperadas detectadas, todas com fonte de evidência.")
        else:
            st.warning(f"Avaliação do caso de teste: {evaluation['matched']} de {evaluation['expected']} ocorrências correspondentes.")
    st.markdown("#### Apuração simulada")
    st.table([
        {"Tributo": "PIS/Pasep", "Calculado": (calc["computed"] or {}).get("pis_pasep"), "Informado": (calc["declared"] or {}).get("pis_pasep"), "Diferença": (calc["difference"] or {}).get("pis_pasep")},
        {"Tributo": "Cofins", "Calculado": (calc["computed"] or {}).get("cofins"), "Informado": (calc["declared"] or {}).get("cofins"), "Diferença": (calc["difference"] or {}).get("cofins")},
    ])
    queue = result.get("review_queue", [])
    client_candidates = sum(item["action"] == "solicitar_documento" for item in queue)
    st.markdown("#### Fila de revisão por documento")
    st.caption(f"{len(queue)} documentos com pendências · {client_candidates} "
               f"{'pedido' if client_candidates == 1 else 'pedidos'} de documento {'sugerido' if client_candidates == 1 else 'sugeridos'} · "
               "as demais divergências exigem revisão interna antes do contato com o cliente.")
    st.dataframe([
        {"Chave": item["access_key"], "Prioridade": SEVERITY_LABELS.get(item["priority"], item["priority"]),
         "Ocorrências": item["occurrence_count"], "Motivos": "; ".join(item["reasons"]),
         "Ação sugerida": "Solicitar documento" if item["action"] == "solicitar_documento" else "Revisar internamente"}
        for item in queue
    ], width="stretch", hide_index=True)
    with st.expander("Ver ocorrências e evidências individuais"):
        st.dataframe([
            {"Regra": RULE_LABELS.get(item["rule_id"], item["rule_id"]), "Severidade": SEVERITY_LABELS.get(item["severity"], item["severity"]), "Descrição": item["message"],
             "Chave": item["access_key"], "Fonte": item["evidence"].get("source_path")}
            for item in result["occurrences"]
        ], width="stretch", hide_index=True)
    st.markdown("#### Preparar contato com o cliente")
    st.caption("Selecione em lote os documentos já conferidos. Apenas pedidos de XML ausente vêm selecionados como sugestão.")
    queue_by_key = {item["access_key"] or item["occurrence_ids"][0]: item for item in queue}
    selected_keys = st.multiselect(
        "Documentos a incluir na prévia",
        options=list(queue_by_key),
        default=[key for key, item in queue_by_key.items() if item["action"] == "solicitar_documento"],
        format_func=lambda key: f"{key} · {', '.join(queue_by_key[key]['reasons'])}",
        key=f"client_selection_{result['case_id']}",
    )
    client_preview = client_brief_text(result["company_name"], result["competencia"],
                                       [queue_by_key[key] for key in selected_keys])
    preview_key = f"client_preview_{result['case_id']}"
    selection_key = f"client_selection_marker_{result['case_id']}"
    if st.session_state.get(selection_key) != selected_keys:
        st.session_state.pop(preview_key, None)
        st.session_state[selection_key] = selected_keys
    edited_preview = st.text_area("Prévia editável para revisão", value=client_preview, height=220,
                                  key=preview_key)
    st.markdown("#### Baixar resultados")
    report_files = ["report.html", "result.json", "occurrences.csv", "triagem.csv", "previa-cliente.txt", "calculation.json", "normalized.json"]
    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipped:
        for filename in report_files:
            zipped.write(output / filename, arcname=filename)
    st.download_button("Baixar pacote completo", archive.getvalue(), file_name=f"{result['case_id']}-resultados.zip", mime="application/zip", type="primary", on_click="ignore")
    left, right = st.columns(2)
    with left:
        st.download_button("Relatório HTML", (output / "report.html").read_bytes(), file_name="report.html", mime="text/html", on_click="ignore")
    with right:
        st.download_button("Ocorrências CSV", (output / "occurrences.csv").read_bytes(), file_name="occurrences.csv", mime="text/csv", on_click="ignore")
    left, right = st.columns(2)
    with left:
        st.download_button("Triagem por documento CSV", (output / "triagem.csv").read_bytes(), file_name="triagem.csv", mime="text/csv", on_click="ignore")
    with right:
        st.download_button("Prévia para o cliente", edited_preview, file_name="previa-cliente.txt", mime="text/plain", on_click="ignore")
