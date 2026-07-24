{
    "name": "FIQ Salgsordre",
    "version": "19.0.1.3.1",
    "summary": "FIQ GUI-skjelett for flaten CRM salgsordre – OWL klient-handling "
    "(placeholder-dashbord), menuitem og rettighetsgruppe. Klar for ekte funksjonalitet.",
    "description": """
FIQ GUI CRM salgsordre
======================
Minimalt, installerbart skjelett i FIQ GUI-familien (jf. fiq_gui_hoved):

 * OWL klient-handling «FIQ GUI CRM salgsordre» – enkel placeholder-side («Kommer»).
 * Menuitem som åpner flaten.
 * Rettighetsgruppe (arver base.group_user).

Bygd rent og konsistent med Hovedmeny-stilen, klart for å fylles med ekte funksjonalitet.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    "depends": ["fiq_gui_control", "web", "sale"],
    "data": [
        "security/fiq_gui_crm_so_groups.xml",
        "views/fiq_gui_crm_so_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Odoo 20-regel 30/31 (Gjermund 23.07): assets deklareres EKSPLISITT.
            # Wildcard skjuler lasterekkefolgen — og rekkefolgen mellom skall og flate
            # var nettopp det som felte grensesnittet 18.07. Stil, logikk, maler.
            "fiq_gui_crm_so/static/src/crm_so.scss",
            "fiq_gui_crm_so/static/src/crm_so.js",
            "fiq_gui_crm_so/static/src/crm_so.xml",
        ],
    },
    "application": True,
    "installable": True,
}
