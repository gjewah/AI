# -*- coding: utf-8 -*-
{
    "name": "FIQ Finans",
    "version": "19.0.1.7.0",
    "summary": "AI GUI Finans (2.70) — visningen av AI Finans-Rådgiveren: analyse, "
               "framskrivning, simulator (fortid/nåtid/fremtid), KPI og POG.",
    "description": """
FIQ GUI Finans — flate 2.70
=============================
Flaten er VISNINGEN av rolla «0.00 2.70 AI Finans-Rådgiver» (rolle bak, flate foran).
Ingen parallell logikk: KPI/rapporter gjenbrukes fra Odoo (native-først).

Innhold (UTKAST 01 — rammeverk, ikke ferdig funksjonalitet):
 * Analyse + framskrivning — hvordan går firmaet (styrker/svakheter/forbedring)
 * Simulator i tre tidsakser: 01 Fortid · 02 Nåtid · 03 Fremtid (3/6/12 mnd, A/B-scenario)
 * KPI-rapporter — brukeren velger hvilke (config-drevet)
 * POG-dashbord + URL (fase 7, etter POG-implementering)

Harde regler innebygd i flaten:
 * FAKTA (bokført) skilles SKARPT fra SCENARIO — et scenario presenteres aldri som regnskapstall.
 * Rådgiver, ikke beslutter — ingen automatiske finansielle handlinger.
 * «Hva gjør andre» = bransje-/markedsdata, ALDRI en annen FIQ-kundes tall (tenant-isolasjon).
 * Lønn = egen gate (lønningsansvarlig ≠ regnskap; sensitiv PII).
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    "depends": ["fiq_gui_control", "fiq_gui_shell", "web", "account"],
    "data": [
        "security/fiq_gui_fin_groups.xml",
        "views/fiq_gui_fin_action.xml",
        # Selvregistrering i KR-menyen — MÅ lastes ETTER action-fila (viser til den).
        "data/fiq_gui_fin_flate.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_fin/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
