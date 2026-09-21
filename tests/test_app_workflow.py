"""A interface publica apenas a conferência rápida de relatórios do Domínio."""

import importlib.util
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Instale requirements.txt para testar a interface")
class AppWorkflowTests(unittest.TestCase):
    def test_assessment_screen_separates_delivery_review_and_errors(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15).run()
        next(button for button in app.button if button.label == "Analisar relatórios").click().run()

        self.assertFalse(app.exception)
        self.assertEqual([(item.label, item.value) for item in app.metric], [
            ("Empresas processadas", "8"),
            ("Sem exceções detectadas", "2"),
            ("Para revisar", "5"),
            ("Erro de processamento", "1"),
        ])
        self.assertEqual([item.value for item in app.subheader], [
            "Competência 2026-08",
            "Sem exceções detectadas · priorizar entrega",
            "Fila de revisão",
            "Erros de processamento",
        ])


if __name__ == "__main__":
    unittest.main()
