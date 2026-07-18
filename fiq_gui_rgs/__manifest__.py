# -*- coding: utf-8 -*-
{
    "name": "FIQ Regnskap",
    "version": "19.0.1.3.0",
    "summary": "AI GUI Regnskap (2.80) — visningen av AI Regnskap-Rådgiveren: likviditet, "
               "cashflow, kritiske datoer og tidlig korrigering.",
    "description": """
FIQ GUI Regnskap — flate 2.80
=============================
Flaten er VISNINGEN av rolla «0.00 2.80 AI Regnskap-Rådgiver» (rolle bak, flate foran).
Native-først: tallene eies av Odoo (account.move) — flaten er et LAG, ingen parallell logikk.

Innhold (UTKAST 01 — rammeverk, ikke ferdig funksjonalitet):
 * Oversikt — inngående · utgående · haster · kritisk · ubetalt
 * Cashflow + mulige kritiske likviditetsdatoer
 * Må tas høyde for — lønnskjøring, sosiale avgifter, feriepenger, pensjon
 * Tidlig korrigering — kortere frister, tidligere fakturering

Harde regler innebygd i flaten:
 * «ALDRI gjett — regnskap er juridisk bindende» (rollens egen regel): bokført FAKTA
   skilles skarpt fra FRAMSKRIVNING.
 * Rådgiver, ikke beslutter — ingen automatiske finansielle handlinger.
 * Lønn = egen gate: aggregater vises, individuell lønns-PII ALDRI.
 * Production-posteringer / regnskaps-avslutning / innsending = menneske.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    "depends": ["fiq_gui_control", "web", "account"],
    "data": [
        "security/fiq_gui_rgs_groups.xml",
        "views/fiq_gui_rgs_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_rgs/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
