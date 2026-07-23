# -*- coding: utf-8 -*-
{
    "name": "FIQ Befaring — mobil befaring → romskjema → tilbud → prosjekt",
    "version": "19.0.1.1.0",
    "summary": "Backend-fundament for befaring på salgsmulighet: befaring · rom/romskjema · "
               "funn/avvik. Kobler crm.lead → tilbud (sale.order) → prosjekt (project.project) "
               "med oppgaven «Befaring». Generisk for alle FIQ-kunder, tenant-isolert (company_id "
               "+ record rules), config-drevet. Mobil-flate (PWA/OWL) bygges oppå senere.",
    "description": """
FIQ Befaring — fundament
==========================
Bygger backend-modellene fra befaring_module_spec (Gjermund 2026-06-21):
befaring starter i SALGSPROSESSEN (crm.lead), fanger rom/etasje + foto + talenotat,
genererer romskjema, fyller tilbud, og overføres til prosjektet under oppgaven «Befaring».

Modeller
--------
 * fiq.befaring       — befarings-økt knyttet til salgsmulighet/tilbud/prosjekt.
 * fiq.befaring.rom   — rom-linje (romskjema): navn/etasje/areal/tiltak/foto/talenotat + AI-tiltak NO/EN.
 * fiq.befaring.funn  — funn/avvik/endring per rom (nonconformity), med alvorlighet + status.

API (@api.model / instans)
--------------------------
 * opprett_fra_lead(lead_id)   — start befaring fra en salgsmulighet.
 * get_romskjema_data()        — strukturert romskjema-data (til QWeb/Excel-eksport senere).
 * populer_kalkulator_data()   — mapper rom/tiltak → tilbudslinjer (data; skriv gjøres av overlay).
 * overfor_til_prosjekt()      — finn/opprett oppgaven «Befaring» på prosjektet og koble befaringen dit.

GENERISK KJERNE. Bransjelag (rom-struktur/kalkulator/Excel for entreprenør = SDV) og
mobil PWA-fangst legges som EGNE moduler oppå denne (fiq_befaring_sdv, PWA). Ingen kunde-fork.
Tenant-isolert: hver modell har company_id (default aktivt firma) + global multi-company record rule.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Sales/FIQ",
    "license": "OPL-1",
    "depends": ["base", "mail", "crm", "sale", "project"],
    "data": [
        "security/ir.model.access.csv",
        "security/fiq_befaring_rules.xml",
        "views/fiq_befaring_views.xml",
        "views/fiq_befaring_menu.xml",
    ],
    "application": True,
    "installable": True,
}
