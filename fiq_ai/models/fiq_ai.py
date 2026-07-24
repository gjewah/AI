"""FIQ AI — tynn shim mot Odoo 19 native AI, grunnet med FIQ-kontekst.

Kontrollrommet («Spør AI») kaller ``self.env["fiq.ai"].chat(q)``. Vi delegerer
til den native tjenesten ``LLMApiService`` som ``fiq_ai_claude`` patcher til
Anthropic Messages API (provider «anthropic»). Ingen egen HTTP-klient her — ÉN
AI-vei. Signatur/retur verifisert mot fiqas Staging-koden (fiq_ai_claude-eier,
2026-07-09).

GRUNNING (2026-07-09, spec brain/spor_ai_grounding_spec.md): FIQ-kontekst
injiseres HER (KR-inngangen), ikke i den generiske adapteren — så adapteren
holdes ren for Meldingssenter/Salg. Config-drevet: overstyrbar systemparam
``fiq_ai.system_context`` med modul-konstant ``FIQ_SPORAI_CONTEXT`` som durabel
fallback.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_PROVIDER = "anthropic"
_DEFAULT_MODEL = "claude-sonnet-5"

# Durabel, versjonert FIQ-kontekst (kilde: 00_master_kontekst + moc/0.00 FIQ AI + AI-Organisasjon).
FIQ_SPORAI_CONTEXT = """Du er «Spør AI» — assistenten i FIQ AI-plattformens Kontrollrom. Svar alltid FIQ-bevisst, på norsk (bokmål), konkret og kort.

HVA FIQ AI ER: FIQ AI (også kalt IQ) er en AI-plattform som ligger et NIVÅ OVER alle firmaer — den strukturerer og drifter AI for flere kunde-firmaer. Eier: Gjermund E. Wæhre (FIQ as). Hierarki: FIQ AI (plattform) → firmaer → strukturer. Kjernen er DELT (felles for alle firmaer); hvert firma har sin EGEN isolerte del.

KUNDENE (firmaer UNDER plattformen, likestilt — Vidir er IKKE «hoved»): FIQ AS (012) · Vidir (040) · SDV-konsernet (049 gruppe + selskapene 050/051/052/054) · JPC (060) · JC02/Jarconsult (061) · Loym · m.fl.

MEMBRAN-REGEL (kritisk): Kunnskap kan gå OPP til den delte kjernen; forretningsdata går ALDRI sideveis mellom firmaer. Per-firma-roller støtter sitt eget firma, aldri et annet.

AI-ORGANISASJON: AI-ansatte er «skills» med roller. Øverst: AI-Sjef = IQ (koordinator + minne-gartner for alle AI-ansatte). Under: rådgivere på direktør-nivå — Prosjekt-Rådgiver, IT-Rådgiver (2.90/ERP-Odoo), Finans-Rådgiver (2.70), KS-Rådgiver (2.40), Skill-Rådgiver (2.21), HR/HMS/FU m.fl. + per-firma-instanser (<firmakode> <rolle>) + Sikkerhetsansvarlig (vokter). Generiske roller = 0.00 <rolle>; per firma = <firmakode> <rolle>.

RYGGRAD & PRINSIPPER: Odoo (ERP, Odoo.sh) + SharePoint (dokumenter). Kjerneprinsipper: forbedre gradvis / aldri overskriv / lav kost–høy ROI · konsolidert kjerne + toggle (ALDRI kunde-fork om generisk mulig) · soliditet > snarvei · navn ikke ID · fakta ikke gjetning · norsk bokmål.

Kjenner du ikke et FIQ-spesifikt faktum, si det ærlig — ikke dikt."""


class FiqAi(models.AbstractModel):
    _name = "fiq.ai"
    _description = "FIQ AI — shim mot Odoo 19 native AI (Anthropic via fiq_ai_claude)"

    @api.model
    def chat(self, prompt, system=None, model=None):
        """Enkelt tekstsvar: én streng inn → ren tekst ut, grunnet med FIQ-kontekst.

        system=None → bruk overstyrbar systemparam ``fiq_ai.system_context``, ellers
        modul-konstanten ``FIQ_SPORAI_CONTEXT``. Kaster videre UserError fra native-
        tjenesten (f.eks. manglende API-nøkkel) — «Spør AI» viser feilen i klartekst.
        """
        q = (prompt or "").strip()
        if not q:
            return ""
        if system is None:
            system = (
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("fiq_ai.system_context")
                or FIQ_SPORAI_CONTEXT
            )
        # Importeres lokalt så modul-lasting ikke feiler om «ai» ikke er klar ved import.
        from odoo.addons.ai.utils.llm_api_service import LLMApiService

        svc = LLMApiService(self.env, provider=_PROVIDER)
        response, _to_call, _next_inputs = svc._request_llm(
            model or _DEFAULT_MODEL,
            [system],
            [q],
        )
        text = "\n".join(response or []).strip()
        return text or "(tomt svar)"
