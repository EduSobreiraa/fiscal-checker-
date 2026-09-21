"""Entrada única para a conferência rápida de relatórios do Domínio."""

from pathlib import Path

import streamlit as st

from fiscal_ui.simples_assessment import simples_assessment_page


ROOT = Path(__file__).resolve().parent
SIMPLES_FIXTURES = ROOT / "fixtures/dominio-batch/2026-08"

st.set_page_config(page_title="Conferência Simples", page_icon="📋", layout="wide")
st.markdown("""
<style>
.block-container {max-width:1120px;padding-top:2.5rem;padding-bottom:4rem}
div[data-testid="stMetric"] {background:#F1F9F3;border:1px solid #DCEDE0;border-radius:14px;padding:1rem}
</style>
""", unsafe_allow_html=True)

simples_assessment_page(SIMPLES_FIXTURES)
