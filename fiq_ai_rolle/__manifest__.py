# -*- coding: utf-8 -*-
{
    "name": "FIQ AI Rolle — AI-organisasjon",
    "version": "19.0.1.0.1",
    "summary": "AI-organisasjonens Rolle-modell (Leder/Rådgiver): Q&A-drevet prompt, "
               "redigerbare stillingsbetegnelser, membran-scope. Menneske-redigerbar (CRUD, ingen kode). "
               "Huses av AI KR-org-kartet; vedlikeholdes av AI HR. Tenant-isolert, per-firma utvidbar.",
    "description": """
FIQ AI Rolle — AI-organisasjonen
==================================
Implementerer den godkjente rolle_system UTKAST 01:
 * fiq.ai.rolle — én rolle-definisjon (navn/rolletype/område/skill/ansvar/rådgivere/KPI/
   membran_scope/kadens/aktiv). Samme rettighetssystem styrer AI-ansatte som mennesker.
 * fiq.ai.rolle.qa — strukturert Q&A. AI-ansvarlig SVARER; skriver ikke prompt.
 * prompt komponeres AUTOMATISK fra Q&A + skill (oppdateres når svar endres).
 * Menneske-redigerbar CRUD (native views + meny «AI-organisasjon»).

Grunnlag for AI KR org-kart (D6) + redigerbare stillingsbetegnelser (D7). Tenant-isolert
(company_id) + per-firma utvidbar/levende. Vedlikeholdes av AI HR.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/fiq_ai_rolle_views.xml",
    ],
    "application": False,
    "installable": True,
}
