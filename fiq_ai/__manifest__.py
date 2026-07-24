{
    "name": "FIQ AI (shim → native Odoo 19 AI)",
    "summary": "Tynn fiq.ai.chat(q)→str som delegerer til Odoo 19 native AI (Anthropic via fiq_ai_claude).",
    "description": """
FIQ AI — tynn shim
==================
Gir modellen ``fiq.ai`` med metoden ``chat(q) -> str`` som Kontrollrommet
(fiq_gui_control «Spør AI») kaller. Delegerer til Odoo 19s native AI-tjeneste
(``ai.utils.llm_api_service.LLMApiService``), som ``fiq_ai_claude`` patcher til
Anthropic Messages API. ÉN AI-vei, ingen egen HTTP-klient her.

Nøkkel/base-URL settes som systemparametere (Gjermund): ``ai.anthropic_key`` /
``ai.anthropic_base_url``. Uten nøkkel kaster native-tjenesten UserError, som
«Spør AI» viser i klartekst.
""",
    "version": "19.0.1.3.2",
    "category": "Productivity/AI",
    "author": "FIQ AS",
    "license": "OPL-1",
    "depends": ["fiq_ai_claude"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/fiq_ai_setup_views.xml",
    ],
    "installable": True,
    "application": False,
}
