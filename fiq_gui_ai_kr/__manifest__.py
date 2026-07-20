# -*- coding: utf-8 -*-
{
    "name": "FIQ AI KR – AI Kontrollrom",
    "version": "19.0.2.11.0",
    "summary": "FIQ AI Kontrollrom (AI KR) – operatør-cockpit: oversikt over alle AI-økter "
               "(Claude Code + Cowork), AI-organisasjonskart, redigerbare roller/skills, "
               "ressursbruk og ROI. Snippet-basert (firma → rolle → person).",
    "description": """
FIQ AI KR – AI Kontrollrom
==========================
Operatør-cockpit for FIQ AI-plattformen. Bygger VIDERE på eksisterende grunnlag
(get_cockpit i fiq_gui_control + fiq_ai/fiq_ai_claude) – aldri fra scratch.

Increment 2.01 (denne versjonen): data-lag for OPPGAVE-OVERSIKT – samler alle
AI-økter/oppgaver (Claude Code + Cowork) som er logget i Odoo, med 👤/🤖-merke,
status og «krever handling». Config-drevet rot-prosjekt (systemparameter
fiq_gui_ai_kr.okter_project_id), firma-scoping klar for firma-snippet.

19.0.2.1.0 — NATIVE VIEWS for øktregisteret (KANON «Odoo-native først», Gjermund 16.07.2026):
`fiq.ai.okt` fantes som modell + registrer_okt(), men UTEN egne views — øktregisteret var
usynlig i Odoo uten KR-flaten. Testen «Virker dette i native Odoo uten KR?» besto ikke.
Nå: liste (farget på status) · skjema · søk m/ filtre (aktive/pause/feilet/**stille >1 døgn**)
+ gruppering (status/kilde/firma/dag) · menypunkt «AI-økter» under AI Kontrollrom-roten.
TVILLING-PRINSIPPET: dette er `brain/okt_register.md` som LEVENDE Odoo-tabell. Claude fører
den selv — Gjermund rører den aldri. Løser den dokumenterte floka med utdaterte økt-id-er
i md-registeret (AI PK-raden pekte 16.07.2026 på en id som ikke finnes).

Kommer i senere increments:
 * AI-organisasjonskart (roller/skills som AI-ansatte per firma)
 * Redigerbare stillingsbetegnelser på roller + skills (rådgivere) – CRUD uten kode
 * Ressursbruk (tokens/USD) + ROI – via Anthropic Admin API (menneske-gate: Admin-nøkkel)
 * Snippet-rammeverk – sett sammen delene selv, per firma / rolle / person

Add-only: rører IKKE den frosne KR-kjernen (fiq_gui_control 6.7xx). Plugges inn
som flate i det delte skallet (Vei C).
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    "depends": ["fiq_gui_control", "fiq_gui_comm", "web", "project", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/ai_kr_action.xml",
        "views/fiq_ai_okt_views.xml",
        "views/fiq_ai_spor_views.xml",
        "views/fiq_ai_melding_views.xml",
        "data/fiq_ai_spor_data.xml",
        "data/fiq_gui_ai_kr_flate.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_ai_kr/static/src/**/*",
        ],
    },
    "application": False,
    "installable": True,
}
