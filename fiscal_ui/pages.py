from __future__ import annotations

import json
from html import escape
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st

from fiscal_engine.case_io import UPLOAD_TYPES
from fiscal_engine.presentation import RULE_LABELS, SEVERITY_LABELS, user_error
from fiscal_engine.reports import render_html
from fiscal_engine.triage import client_brief_text
from fiscal_engine.workspace import PORTALS, REVIEW_STATUSES, Workspace, csv_download


CSV_LABELS = {
    "nfe_csv": "NF-e e itens — nfe.csv",
    "escrituracao_reduzida_csv": "Escrituração — lancamentos.csv",
    "valor_informado_csv": "Valores informados — valor_informado.csv",
    "nfe_event_csv": "Eventos — eventos.csv",
    "produtos_csv": "Produtos — produtos.csv",
    "participantes_csv": "Participantes — participantes.csv",
}


def company_label(company: dict) -> str:
    return f"{company['name']} · {company['tax_id']}"


def choose_company(workspace: Workspace, key: str) -> dict | None:
    companies = {company["id"]: company for company in workspace.companies()}
    if not companies:
        st.info("Cadastre uma empresa ou carregue a demonstração na página Empresas para começar.")
        return None
    identifier = st.selectbox("Empresa", list(companies), format_func=lambda value: company_label(companies[value]), key=key)
    return companies[identifier]


def home(workspace: Workspace):
    st.title("Sua carteira, organizada por exceções")
    st.write("Use o Domínio como referência dos documentos e concentre a revisão nas pendências de cada empresa.")
    a, b, c = st.columns(3)
    a.metric("Empresas cadastradas", len(workspace.companies()))
    b.metric("Execuções salvas", len(workspace.batches()))
    c.metric("Conectores de coleta ativos", 0)
    manual, automatic = st.columns(2)
    with manual, st.container(border=True):
        st.subheader("Manual")
        st.write("Importe os CSVs de uma empresa, consulte o inventário e gere um relatório para conferência. Os mesmos arquivos ficam disponíveis para a análise em lote.")
        st.button("Abrir modo manual", width="stretch", on_click=lambda: st.session_state.update(navigation="Manual"))
    with automatic, st.container(border=True):
        st.subheader("Automático")
        st.write("Selecione empresas e competência para analisar os inventários disponíveis e reunir as divergências em uma fila de trabalho.")
        st.button("Abrir modo automático", type="primary", width="stretch", on_click=lambda: st.session_state.update(navigation="Automático"))
    st.info("Nesta etapa, a entrada vem de arquivos. A conexão direta com JettaX, ONVIO e portais ainda não está disponível.")
    st.caption("O catálogo guarda referências, resultados e decisões. Uma importação idêntica é reaproveitada; a análise não cria novas cópias das notas.")


def companies_page(workspace: Workspace, demo: Path, cases_root: Path):
    st.title("Empresas")
    st.write("Organize a carteira e registre o código usado no Domínio para localizar a empresa na origem.")
    companies = workspace.companies()
    if companies:
        st.dataframe([{"Empresa": c["name"], "CNPJ": c["tax_id"], "Código no Domínio": c["domain_ref"], "Município / UF": c["municipality"]} for c in companies], hide_index=True, width="stretch")
    options = {"new": None, **{c["id"]: c for c in companies}}
    chosen = st.selectbox("Cadastro", list(options), format_func=lambda value: "Nova empresa" if value == "new" else company_label(options[value]))
    current = options[chosen] or {}
    with st.form(f"company_{chosen}"):
        name = st.text_input("Nome da empresa", value=current.get("name", ""))
        tax_id = st.text_input("CNPJ", value=current.get("tax_id", ""), disabled=chosen != "new")
        a, b = st.columns(2)
        domain_ref = a.text_input("Código da empresa no Domínio", value=current.get("domain_ref", ""))
        municipality = b.text_input("Município / UF", value=current.get("municipality", ""))
        if st.form_submit_button("Salvar empresa", type="primary"):
            try:
                workspace.save_company(name, tax_id, domain_ref, municipality)
                st.session_state["flash"] = "Empresa salva."
                st.rerun()
            except (OSError, ValueError) as exc:
                st.error(user_error(exc))
    with st.expander("Demonstração e casos existentes"):
        st.write("A demonstração vincula o caso sintético existente sem copiar seus arquivos.")
        if st.button("Carregar empresa de demonstração"):
            metadata = json.loads((demo / "metadata.json").read_text(encoding="utf-8"))
            existing = next((c for c in companies if c["tax_id"] == metadata["company_tax_id"]), None)
            identifier = existing["id"] if existing else workspace.save_company(metadata["company_name"], metadata["company_tax_id"], "DEMO", "Salvador / BA")
            workspace.register_reference(identifier, metadata["competencia"], demo, "Demonstração", "Caso sintético do projeto")
            st.session_state["flash"] = "Demonstração disponível no modo manual e automático, competência 2026-08."
            st.rerun()
        paths = sorted(path for path in cases_root.glob("*/metadata.json") if not path.parent.name.startswith("."))
        if paths:
            selected = st.selectbox("Caso já salvo neste computador", paths, format_func=lambda p: p.parent.name)
            if st.button("Vincular caso existente"):
                try:
                    metadata = json.loads(selected.read_text(encoding="utf-8"))
                    existing = next((c for c in companies if c["tax_id"] == metadata["company_tax_id"]), None)
                    identifier = existing["id"] if existing else workspace.save_company(metadata["company_name"], metadata["company_tax_id"])
                    workspace.register_reference(identifier, metadata["competencia"], selected.parent, "Importação local", "Caso existente")
                    st.session_state["flash"] = "Caso vinculado sem duplicar os arquivos."
                    st.rerun()
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    st.error(user_error(exc))


def manual_page(workspace: Workspace, demo: Path):
    st.title("Manual · inventário da empresa")
    company = choose_company(workspace, "manual_company")
    if not company:
        return
    period = st.text_input("Competência (AAAA-MM)", value="2026-08", key="manual_period")
    st.caption(f"Referência no Domínio: {company['domain_ref'] or 'não informada'} · {company['municipality'] or 'município não informado'}")
    inventory_tab, import_tab = st.tabs(["Inventário e versões", "Importar arquivos"])
    with import_tab:
        st.subheader("Importar uma exportação")
        st.write("Cada importação representa uma versão completa do inventário da competência. Para complementar uma versão, envie novamente o conjunto completo; as versões anteriores continuam disponíveis para consulta.")
        st.info("CSVs devem seguir o modelo abaixo: UTF-8, vírgula como separador e ponto decimal. Exportações do Domínio precisam ter as colunas correspondentes; o layout nativo ainda depende de validação com um arquivo de exemplo.")
        examples = BytesIO()
        with ZipFile(examples, "w", ZIP_DEFLATED) as zipped:
            for sample in sorted((demo / "raw").rglob("*.csv")):
                zipped.write(sample, arcname=sample.name)
        st.download_button("Baixar modelos de CSV", examples.getvalue(), "modelos-fiscal-checker.zip", "application/zip")
        with st.expander("Conferir colunas aceitas"):
            for kind, label in CSV_LABELS.items():
                sample = demo / UPLOAD_TYPES[kind]
                st.markdown(f"**{label}**")
                st.code(sample.read_text(encoding="utf-8-sig").splitlines()[0], language=None, wrap_lines=True)
        with st.form(f"import_{company['id']}_{period}", clear_on_submit=True):
            origin = st.selectbox("Origem dos arquivos", ["Domínio — exportação CSV", "Importação local", "JettaX — exportação", "ONVIO — exportação"])
            reference = st.text_input("Referência da exportação", placeholder="Ex.: fechamento de agosto / lote 123")
            notes = st.file_uploader(CSV_LABELS["nfe_csv"], type="csv", max_upload_size=10)
            with st.expander("Alternativa: notas e eventos em XML"):
                xmls = st.file_uploader("XMLs de NF-e modelo 55 e eventos", type="xml", accept_multiple_files=True, max_upload_size=10)
                st.caption("Até 200 arquivos, total da importação até 50 MiB. Use CSV ou XML para as notas.")
            st.markdown("**Complementos para a análise**")
            st.caption("Sem escrituração e valores informados, o inventário pode ser consultado, mas a análise fica incompleta.")
            uploads = {"nfe_csv": notes}
            for kind in ("escrituracao_reduzida_csv", "valor_informado_csv", "nfe_event_csv", "produtos_csv", "participantes_csv"):
                uploads[kind] = st.file_uploader(CSV_LABELS[kind], type="csv", max_upload_size=10)
            if st.form_submit_button("Salvar inventário", type="primary"):
                try:
                    workspace.import_files(company["id"], period,
                                           {kind: upload.getvalue() for kind, upload in uploads.items() if upload is not None},
                                           [(upload.name, upload.getvalue()) for upload in xmls], demo / "config/tax_profile.json", origin, reference)
                    st.session_state["flash"] = "Inventário disponível. Conteúdos idênticos são reaproveitados."
                    st.rerun()
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    st.error(user_error(exc))
    with inventory_tab:
        snapshots = {row["id"]: row for row in workspace.snapshots(company["id"], period)}
        if not snapshots:
            st.info("Nenhum inventário para esta competência. Use a aba Importar arquivos.")
            return
        active_id = next((key for key, row in snapshots.items() if row["active"]), next(iter(snapshots)))
        identifier = st.selectbox("Versão do inventário", list(snapshots), index=list(snapshots).index(active_id),
                                  format_func=lambda value: f"{'Ativa · ' if snapshots[value]['active'] else ''}{snapshots[value]['created_at'][:19].replace('T', ' ')} UTC · {snapshots[value]['origin']} · {value[:8]}",
                                  key=f"snapshot_{company['id']}_{period}")
        snapshot = snapshots[identifier]
        st.caption("A análise em lote utiliza a versão ativa. Trocar a versão não apaga arquivos nem o histórico de revisão.")
        if not snapshot["active"] and st.button("Usar esta versão nas próximas análises"):
            workspace.activate(identifier)
            st.rerun()
        try:
            rows, errors = workspace.inventory(identifier)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            st.error(user_error(exc))
            return
        a, b, c = st.columns(3)
        a.metric("Chaves no inventário", len(rows))
        b.metric("Chaves repetidas", sum(row["Registros"] > 1 for row in rows))
        c.metric("Canceladas", sum(row["Situação"] == "Cancelada" for row in rows))
        query = st.text_input("Buscar chave de acesso", key="inventory_search")
        only_issues = st.checkbox("Mostrar apenas repetidas, canceladas ou fora da competência")
        filtered = [row for row in rows if query.strip() in row["Chave"] and (not only_issues or row["Registros"] > 1 or row["Situação"] != "Autorizada" or row["Fora da competência"])]
        st.dataframe(filtered, hide_index=True, width="stretch")
        for error in errors:
            st.warning(f"{error['source_path']}: {error['message']}")
        st.caption("O inventário descreve os arquivos disponíveis. Não confirma que todos os documentos existentes no Domínio ou nos portais foram recebidos.")
        export_rows = [{"Empresa": company["name"], "CNPJ": company["tax_id"], **row} for row in rows]
        fields = list(export_rows[0]) if export_rows else ["Empresa", "CNPJ", "Chave"]
        st.download_button("Baixar inventário completo CSV", csv_download(export_rows, fields), f"inventario-{company['tax_id']}-{period}.csv", "text/csv")
        if st.button("Analisar inventário desta versão", type="primary"):
            if not snapshot["active"]:
                st.warning("Ative esta versão para analisá-la.")
            else:
                with st.spinner("Analisando documentos disponíveis..."):
                    batch = workspace.run_batch([company["id"]], period, [])
                st.session_state["selected_batch"] = batch["id"]
                st.session_state["pending_navigation"] = "Pendências"
                st.rerun()


def automatic_page(workspace: Workspace):
    st.title("Automático · análise em lote")
    companies = {company["id"]: company for company in workspace.companies()}
    if not companies:
        st.info("Cadastre empresas ou carregue a demonstração na página Empresas.")
        return
    st.write("Analise os inventários ativos de várias empresas e acompanhe as exceções em uma única fila.")
    with st.form("batch"):
        selected = st.multiselect("Empresas para analisar", list(companies), default=list(companies), format_func=lambda value: company_label(companies[value]))
        period = st.text_input("Competência (AAAA-MM)", value="2026-08")
        portals = st.multiselect("Consultas externas desejadas", PORTALS, help="Selecione somente se quiser registrar a necessidade de consulta no relatório. Os conectores ainda não estão disponíveis.")
        st.info("A análise dos arquivos importados funciona agora. Consultas a Domínio, SEFAZ, Portal Nacional e prefeitura ficam pendentes de integração. JettaX/ONVIO serão fontes futuras de coleta.")
        st.caption("Uma consulta externa pendente mantém a análise como incompleta, mesmo que os arquivos disponíveis não apresentem divergências.")
        submitted = st.form_submit_button("Analisar empresas selecionadas", type="primary")
    if submitted:
        try:
            progress = st.progress(0, text="Preparando análise...")
            batch = workspace.run_batch(selected, period, portals,
                                        lambda done, total: progress.progress(done / total, text=f"{done} de {total} empresas processadas"))
            st.session_state["selected_batch"] = batch["id"]
            st.success("Execução salva. Consulte os resultados abaixo ou na fila de pendências.")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            st.error(user_error(exc))
    if st.session_state.get("selected_batch"):
        show_batch(workspace, workspace.batch(st.session_state["selected_batch"]), review=False)


def report_bundle(workspace: Workspace, batch: dict) -> bytes:
    """Relatórios gerados sob demanda, sem novos arquivos permanentes."""
    output = BytesIO()
    overview = [f"<h1>Análise em lote · {escape(batch['period'])}</h1>",
                f"<p>Execução: {escape(batch['created_at'])}</p>",
                "<p>Verificações do protótipo com parâmetros fictícios. Ausência de divergências não confirma regularidade fiscal.</p>"]
    findings = []
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for item in batch["items"]:
            overview.append(f"<h2>{escape(item['company_name'])} · {escape(item['tax_id'])}</h2><p>{escape(item['status'])}</p>")
            coverage = "<h2>Cobertura da execução</h2><ul>" + "".join(f"<li>{escape(source['source'])}: {escape(source['status'])} — {escape(source['detail'])}</li>" for source in item["coverage"]) + "</ul>"
            error = f"<p>{escape(item['error'])}</p>" if item["error"] else ""
            overview.extend([coverage, error])
            result = item["result"]
            if result:
                reviews = workspace.reviews(item["snapshot_id"])
                filename = f"{item['tax_id']}/relatorio.html"
                overview.append(f'<p><a href="{filename}">Relatório detalhado da empresa</a></p>')
                report = render_html(result).replace("<body>", f"<body><p>Situação do lote: {escape(item['status'])}</p>{coverage}{error}", 1)
                archive.writestr(filename, report)
                archive.writestr(f"{item['tax_id']}/resultado.json", json.dumps(result, ensure_ascii=False, indent=2))
                for finding in result["occurrences"]:
                    review = reviews.get(finding["occurrence_id"], {"status": "Pendente", "note": ""})
                    findings.append({"Empresa": item["company_name"], "CNPJ": item["tax_id"], "Competência": batch["period"],
                                     "Chave": finding["access_key"], "Regra": RULE_LABELS.get(finding["rule_id"], finding["rule_id"]),
                                     "Gravidade": SEVERITY_LABELS.get(finding["severity"], finding["severity"]), "Descrição": finding["message"],
                                     "Evidência": json.dumps(finding["evidence"], ensure_ascii=False), "Situação": review["status"], "Tratamento": review["note"]})
        fields = list(findings[0]) if findings else ["Empresa", "CNPJ", "Competência", "Chave", "Regra", "Situação"]
        archive.writestr("pendencias.csv", csv_download(findings, fields))
        archive.writestr("execucao.json", json.dumps(batch, ensure_ascii=False, indent=2))
        archive.writestr("resumo.html", '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Análise em lote</title><body>' + "".join(overview) + "</body></html>")
    return output.getvalue()


def show_batch(workspace: Workspace, batch: dict, review: bool = True):
    st.subheader(f"Resultado · {batch['period']}")
    st.caption(f"Execução em {batch['created_at'][:19].replace('T', ' ')} UTC. Resultados descrevem os arquivos daquela execução.")
    summary = []
    for item in batch["items"]:
        result = item["result"]
        summary.append({"Empresa": item["company_name"], "CNPJ": item["tax_id"], "Situação": item["status"],
                        "Documentos": result["summary"]["documents"] if result else None,
                        "Divergências": len(result["occurrences"]) if result else None,
                        "Erros de entrada": result["summary"]["input_errors"] if result else None,
                        "Observação": item["error"]})
    st.dataframe(summary, hide_index=True, width="stretch")
    st.download_button("Baixar relatório completo do lote", report_bundle(workspace, batch), f"analise-{batch['period']}-{batch['id'][:8]}.zip", "application/zip")
    with st.expander("Cobertura das fontes e limitações"):
        for item in batch["items"]:
            st.markdown(f"**{item['company_name']}**")
            if item["error"]:
                st.warning(item["error"])
            st.dataframe([{"Fonte": c["source"], "Situação": c["status"], "Detalhe": c["detail"]} for c in item["coverage"]], hide_index=True)
            if item["result"]:
                for error in item["result"]["input_errors"]:
                    st.warning(f"{error['source_path']}: {error['message']}")
                for limitation in item["result"]["calculation"]["limitations"]:
                    st.caption(limitation)
    if not review:
        st.button("Tratar pendências deste lote", on_click=lambda: st.session_state.update(navigation="Pendências"))
        return
    a, b, c = st.columns(3)
    company_filter = a.selectbox("Filtrar empresa", ["Todas"] + [item["company_name"] + " · " + item["tax_id"] for item in batch["items"]])
    severity = b.selectbox("Gravidade", ["Todas", *SEVERITY_LABELS.values()])
    show_resolved = c.checkbox("Incluir resolvidas")
    rule_filter = st.selectbox("Tipo de divergência", ["Todos", *sorted({RULE_LABELS.get(finding["rule_id"], finding["rule_id"]) for item in batch["items"] if item["result"] for finding in item["result"]["occurrences"]})])
    entries = []
    for item in batch["items"]:
        if not item["result"] or (company_filter != "Todas" and company_filter != item["company_name"] + " · " + item["tax_id"]):
            continue
        reviews = workspace.reviews(item["snapshot_id"])
        for finding in item["result"]["occurrences"]:
            state = reviews.get(finding["occurrence_id"], {"status": "Pendente", "note": ""})
            if state["status"] == "Resolvido" and not show_resolved:
                continue
            if severity != "Todas" and SEVERITY_LABELS.get(finding["severity"]) != severity:
                continue
            if rule_filter != "Todos" and RULE_LABELS.get(finding["rule_id"], finding["rule_id"]) != rule_filter:
                continue
            entries.append((item, finding, state))
    st.subheader(f"Fila de tratamento · {len(entries)} ocorrências")
    if not entries:
        st.info("Nenhuma ocorrência para os filtros atuais. Confira também as análises incompletas e a cobertura das fontes acima.")
    else:
        st.dataframe([{"Empresa": item["company_name"], "Chave": finding["access_key"],
                       "Gravidade": SEVERITY_LABELS.get(finding["severity"]), "Motivo": RULE_LABELS.get(finding["rule_id"], finding["rule_id"]),
                       "Situação": state["status"]} for item, finding, state in entries], hide_index=True, width="stretch")
        selected = st.selectbox("Abrir pendência", range(len(entries)), format_func=lambda index: f"{entries[index][0]['company_name']} · {RULE_LABELS.get(entries[index][1]['rule_id'], entries[index][1]['rule_id'])} · {entries[index][1]['access_key'] or 'Geral'}")
        item, finding, state = entries[selected]
        st.write(finding["message"])
        with st.expander("Evidências e valores", expanded=True):
            st.write({"Esperado": finding["expected_value"], "Encontrado": finding["declared_value"]})
            st.json(finding["evidence"])
        with st.form(f"review_{item['snapshot_id']}_{finding['occurrence_id']}"):
            status = st.selectbox("Situação do tratamento", REVIEW_STATUSES, index=REVIEW_STATUSES.index(state["status"]))
            note = st.text_area("Anotação do analista", value=state["note"], help="Para resolver, descreva a conferência ou correção realizada na origem.")
            if st.form_submit_button("Salvar tratamento", type="primary"):
                try:
                    workspace.save_review(item["snapshot_id"], finding["occurrence_id"], status, note)
                    st.session_state["flash"] = "Tratamento salvo. As correções nos documentos devem ser realizadas na origem."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with st.expander("Histórico do tratamento"):
            st.dataframe(workspace.review_history(item["snapshot_id"], finding["occurrence_id"]), hide_index=True)
    successful = [item for item in batch["items"] if item["result"]]
    if successful:
        with st.expander("Preparar contato com o cliente"):
            chosen = st.selectbox("Empresa para a prévia", range(len(successful)), format_func=lambda index: successful[index]["company_name"])
            item = successful[chosen]
            queue = item["result"].get("review_queue", [])
            selected = st.multiselect("Documentos para incluir", range(len(queue)), format_func=lambda index: f"{queue[index]['access_key'] or 'Geral'} · {'; '.join(queue[index]['reasons'])}", key=f"brief_selection_{batch['id']}_{item['company_id']}")
            preview = client_brief_text(item["company_name"], batch["period"], [queue[index] for index in selected])
            edited = st.text_area("Prévia editável", value=preview, height=220, key=f"brief_{batch['id']}_{item['company_id']}_{selected}")
            st.download_button("Baixar prévia para revisão", edited, f"previa-{item['tax_id']}.txt", "text/plain")


def review_page(workspace: Workspace):
    st.title("Pendências e histórico")
    batches = workspace.batches()
    if not batches:
        st.info("Execute uma análise no modo manual ou automático para abrir a fila de trabalho.")
        return
    ids = [batch["id"] for batch in batches]
    lookup = {batch["id"]: batch for batch in batches}
    current = st.session_state.get("selected_batch", ids[0])
    chosen = st.selectbox("Execução", ids, index=ids.index(current) if current in ids else 0,
                          format_func=lambda value: lookup[value]["created_at"][:19].replace("T", " ") + " UTC · " + value[:8])
    st.session_state["selected_batch"] = chosen
    show_batch(workspace, workspace.batch(chosen))
