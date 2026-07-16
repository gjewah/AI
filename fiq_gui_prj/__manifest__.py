# -*- coding: utf-8 -*-
{
    "name": "FIQ Prosjekt",
    "version": "19.0.1.3.0",
    "summary": "FIQ Prosjekt – native disposisjonsnummer (WBS) på oppgaver, "
               "synlig i Odoos egne list-/skjema-/søkevisninger. GUI-flate på vei.",
    "description": """
FIQ GUI Prosjekt
===================
KANON «Odoo-native først» (Gjermund 2026-07-16): KR er et LAG, ikke systemet.
Testen: «Virker dette i native Odoo uten KR?» — feltene her er ekte Odoo-felt
med Odoo-visning. Slås KR av, står de fortsatt.

Denne versjonen (19.0.1.3.0):
 * NYTT native felt `fiq_wbs_number` på project.task — dynamisk disposisjonsnummer
   (01, 01.02). Rekalkuleres ved flytting i treet; store+indeksert.
 * Synlig i Odoos EGNE views: liste (optional=show), skjema, søk/gruppering.
 * Nummer-modellen respektert: `code` (oppgavenr.) og `sequence_code` (prosjektnr.)
   er STABILE og røres aldri — kun WBS er dynamisk.

Fra før:
 * OWL klient-handling «FIQ GUI Prosjekt» (placeholder-flate).
 * Rettighetsgruppe (arver base.group_user).
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    "depends": ["fiq_gui_control", "web", "project"],
    "data": [
        "security/fiq_gui_prj_groups.xml",
        "views/fiq_gui_prj_action.xml",
        "views/project_task_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_prj/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
