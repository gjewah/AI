# -*- coding: utf-8 -*-
"""FIQ AI — tynn shim mot Odoo 19 native AI.

Kontrollrommet («Spør AI») kaller ``self.env["fiq.ai"].chat(q)``. Vi delegerer
til den native tjenesten ``LLMApiService`` som ``fiq_ai_claude`` patcher til
Anthropic Messages API (provider «anthropic»). Ingen egen HTTP-klient her — ÉN
AI-vei. Signatur/retur verifisert mot fiqas Staging-koden (fiq_ai_claude-eier,
2026-07-09).
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Native provider-navn (= ClaudeProvider.NAME i fiq_ai_claude) og standardmodell.
_PROVIDER = "anthropic"
_DEFAULT_MODEL = "claude-sonnet-5"
_DEFAULT_SYSTEM = "Du er FIQ AI-assistent. Svar kort og presist på norsk bokmål."


class FiqAi(models.AbstractModel):
    _name = "fiq.ai"
    _description = "FIQ AI — shim mot Odoo 19 native AI (Anthropic via fiq_ai_claude)"

    @api.model
    def chat(self, prompt, system=None, model=None):
        """Enkelt tekstsvar: én streng inn → ren tekst ut.

        Kaster videre UserError fra native-tjenesten (f.eks. manglende
        API-nøkkel) — «Spør AI» viser feilen i klartekst.
        """
        q = (prompt or "").strip()
        if not q:
            return ""
        # Importeres lokalt så modul-lasting ikke feiler om «ai» ikke er klar ved import.
        from odoo.addons.ai.utils.llm_api_service import LLMApiService

        svc = LLMApiService(self.env, provider=_PROVIDER)
        response, _to_call, _next_inputs = svc._request_llm(
            model or _DEFAULT_MODEL,
            [system or _DEFAULT_SYSTEM],
            [q],
        )
        text = "\n".join(response or []).strip()
        return text or "(tomt svar)"
