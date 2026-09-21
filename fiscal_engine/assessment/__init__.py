"""Conferência por exceção de relatórios de apuração do Simples Nacional.

Este pacote não calcula tributos nem interpreta PDFs do Domínio. Ele recebe dados
extraídos por adaptadores e verifica a consistência entre as fontes.
"""

from .service import assess_batch, discover_sources

__all__ = ["assess_batch", "discover_sources"]
