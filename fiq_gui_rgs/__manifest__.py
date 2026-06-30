# -*- coding: utf-8 -*-
{
    "name": "FIQ GUI Regnskap",
    "version": "19.0.1.0.0",
    "summary": "FIQ GUI-skjelett for flaten Regnskap – OWL klient-handling "
               "(placeholder-dashbord), menuitem og rettighetsgruppe. Klar for ekte funksjonalitet.",
    "description": """
FIQ GUI Regnskap
===================
Minimalt, installerbart skjelett i FIQ GUI-familien (jf. fiq_gui_hoved):
 * OWL klient-handling «FIQ GUI Regnskap» – enkel placeholder-side («Kommer»).
 * Menuitem som åpner flaten.
 * Rettighetsgruppe (arver base.group_user).
Bygd rent og konsistent med Hovedmeny-stilen, klart for å fylles med ekte funksjonalitet.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    "depends": ["web", "account"],
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
