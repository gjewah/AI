# -*- coding: utf-8 -*-
{
    "name": "FIQ Regnskap",
    "version": "19.0.1.24.0",
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
    "license": "OPL-1",
    # fiq_gui_fin: Regnskap (2.80) ligger som UNDERMENY under Finans (2.70) —
    # Gjermund 18.07.2026: «Finans skal være hoved, Regnskap en undermeny».
    # Uten denne avhengigheten laster ikke Odoo FIN-menyen først → menyrota finnes ikke.
    # Speiler rollehierarkiet: 2.80 rapporterer til 2.70 (CFO).
    "depends": ["fiq_gui_control", "fiq_gui_shell", "fiq_gui_fin", "web", "account"],
    "data": [
        "security/fiq_gui_rgs_groups.xml",
        "views/fiq_gui_rgs_action.xml",
        # Selvregistrering i KR-menyen — MÅ lastes ETTER action-fila (viser til den).
        "data/fiq_gui_rgs_flate.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Odoo 20-regel 30/31 (Gjermund 23.07): assets deklareres EKSPLISITT.
            # Wildcard skjuler lasterekkefolgen — og rekkefolgen mellom skall og flate
            # var nettopp det som felte grensesnittet 18.07. Stil, logikk, maler.
            "fiq_gui_rgs/static/src/rgs.scss",
            "fiq_gui_rgs/static/src/rgs.js",
            "fiq_gui_rgs/static/src/rgs.xml",

        ],
    },
    "application": True,
    "installable": True,
}
