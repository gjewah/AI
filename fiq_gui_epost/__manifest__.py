# -*- coding: utf-8 -*-
{
    "name": "FIQ Kommunikasjon",
    "version": "19.0.1.2.0",
    "summary": "FIQ GUI-skjelett for flaten E-post/Kommunikasjon – OWL klient-handling "
               "(placeholder-dashbord), menuitem og rettighetsgruppe. Klar for ekte funksjonalitet.",
    "description": """
FIQ GUI E-post/Kommunikasjon
===================
Minimalt, installerbart skjelett i FIQ GUI-familien (jf. fiq_gui_hoved):
 * OWL klient-handling «FIQ GUI E-post/Kommunikasjon» – enkel placeholder-side («Kommer»).
 * Menuitem som åpner flaten.
 * Rettighetsgruppe (arver base.group_user).
Bygd rent og konsistent med Hovedmeny-stilen, klart for å fylles med ekte funksjonalitet.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    "depends": ["fiq_gui_control", "web", "mail"],
    "data": [
        "security/fiq_gui_epost_groups.xml",
        "views/fiq_gui_epost_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_epost/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
