"""Entrada única para a conferência rápida de relatórios do Domínio."""

from pathlib import Path

import streamlit as st

from fiscal_ui.simples_assessment import simples_assessment_page


ROOT = Path(__file__).resolve().parent
SIMPLES_FIXTURES = ROOT / "fixtures/dominio-batch/2026-08"

st.set_page_config(page_title="Conferência Simples", page_icon="🌿", layout="wide")
st.markdown("""
<style>
:root {--ink:#173728;--leaf:#2f714b;--leaf-dark:#1d5537;--paper:#f7f8f2;--mist:#e5eee0;--line:#c9d8c8;--gold:#d7b96a;--muted:#5e7163}
.stApp {background:var(--paper);color:var(--ink);font-family:"Aptos", "Segoe UI", sans-serif}
.block-container {max-width:1160px;padding-top:2rem;padding-bottom:3rem}
h1, h2, h3 {font-family:"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;color:var(--ink)}
div[data-testid="stMetric"] {background:transparent;border-left:1px solid var(--line);border-radius:0;padding:.15rem 0 .15rem 1rem;box-shadow:none}
div[data-testid="stMetricLabel"] {color:var(--muted);font-size:.85rem}
div[data-testid="stMetricValue"] {color:var(--leaf-dark);font-family:"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;font-size:2rem}
.hero {display:grid;grid-template-columns:minmax(0,1.65fr) minmax(240px,.75fr);gap:2.2rem;background:var(--mist);border-left:6px solid var(--leaf);padding:2.65rem 2.7rem;margin:0 0 1.25rem}
.hero-context {color:var(--leaf-dark);font-size:.94rem;font-weight:650;margin:0 0 .9rem}
.hero h1 {font-size:clamp(2.4rem,5vw,4.15rem);font-weight:500;letter-spacing:-.045em;line-height:.98;max-width:720px;margin:0 0 1.2rem}
.hero-copy > p:last-child {color:#395343;font-size:1.08rem;line-height:1.65;max-width:650px;margin:0}
.hero-ledger {align-self:stretch;background:#fdfdf9;border:1px solid var(--line);padding:1.25rem 1.3rem}
.ledger-title {color:var(--leaf-dark);font-family:"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;font-size:1.25rem;margin:0 0 .95rem}
.ledger-step {border-top:1px solid #dde6da;color:#435b4a;display:grid;grid-template-columns:2rem 1fr;gap:.55rem;padding:.72rem 0;font-size:.9rem;line-height:1.35}
.ledger-step:last-child {border-bottom:1px solid #dde6da}.ledger-step strong {color:var(--gold);font-family:Georgia,serif;font-size:1.15rem;font-weight:500}
.explainer {display:grid;grid-template-columns:1fr 1.2fr;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:2rem 0 2.25rem;padding:1.6rem 0;gap:3rem}
.explainer h2 {font-size:1.75rem;line-height:1.1;margin:0}.explainer p {color:var(--muted);line-height:1.7;margin:0;max-width:660px}
.section-heading {font-size:1.85rem;margin:0 0 .25rem}.section-intro {color:var(--muted);margin:0 0 1rem}
.quiet-state {background:#eef4ea;border:1px dashed #aac6af;color:#415c48;margin-top:1.1rem;padding:1.1rem 1.25rem;line-height:1.55}.quiet-state strong {color:var(--leaf-dark)}
div[data-testid="stAlert"] {background:#e4f1e2 !important;border:1px solid #bbd6bd !important;border-left:4px solid var(--leaf) !important;border-radius:0;box-shadow:0 8px 18px rgba(29,85,55,.12);color:var(--leaf-dark) !important}
div[data-testid="stAlert"] p, div[data-testid="stAlert"] span {color:var(--leaf-dark) !important;font-weight:700 !important}
div.stButton > button, div.stDownloadButton > button {background:var(--leaf-dark);border:1px solid var(--leaf-dark);border-radius:4px;color:#fff;font-weight:600;padding:.55rem 1rem}
div.stButton > button:hover, div.stDownloadButton > button:hover {background:var(--leaf);border-color:var(--leaf)}
div[data-baseweb="input"] {background:#fff;border-color:var(--line);border-radius:3px}
div[data-baseweb="input"]:focus-within {border-color:var(--leaf);box-shadow:0 0 0 2px rgba(47,113,75,.16)}
.site-footer {border-top:1px solid var(--line);color:var(--muted);font-size:.86rem;margin-top:3.2rem;padding:1.4rem 0 .25rem;text-align:left}
@media (max-width: 760px) {.block-container {padding:1.25rem 1rem 2rem}.hero {grid-template-columns:1fr;padding:1.7rem 1.35rem;gap:1.5rem}.hero h1 {font-size:2.7rem}.explainer {grid-template-columns:1fr;gap:.7rem;padding:1.25rem 0}}
</style>
""", unsafe_allow_html=True)

simples_assessment_page(SIMPLES_FIXTURES)
st.markdown('<footer class="site-footer">Software produzido por Eduardo Sobreira.</footer>', unsafe_allow_html=True)
