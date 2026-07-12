# -*- coding: utf-8 -*-
{
    "name": "FIQ AI KR – AI Kontrollrom",
    "version": "19.0.1.1.0",
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
    "depends": ["fiq_gui_control", "web", "project"],
    "data": [],
    "application": False,
    "installable": True,
}
