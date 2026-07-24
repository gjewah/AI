{
    "name": "Control room",
    "version": "19.0.7.11.9",
    "summary": "Control room – the unified OWL shell (dashboard/landing) that hosts every "
    "main menu as a navigation view: company picker, Simple/Full mode, per-company "
    "accent/logo, KPIs from real Odoo data, communication and dynamic widgets.",
    "description": """
FIQ Control room
================
The canonical control room: ONE OWL client action that is the home shell. Every main
menu (Projects, Communication, CRM, Sales, Accounting, dashboards) is reached as a
navigation VIEW inside this shell – not as separate apps on Odoo's native main menu.

Key features
 * Company picker (top) – switch the active company from the shell.
 * Simple / Full mode – Simple shows the essentials; Full shows advanced widgets.
 * Dark-grey sidebar – standard for every company; only the accent color varies.
 * Per-company branding: accent color + logo set on res.company.
 * KPI row + project overview from real Odoo data (project).
 * Communication view (email/messages) with direction + sender filtering.
 * Fully translatable – English source, Norwegian (nb_NO) provided; follows the user's language.
""",
    "author": "FIQ as",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    "depends": ["web", "project"],
    "data": [
        "security/fiq_gui_control_groups.xml",
        "security/ir.model.access.csv",
        "views/res_company_views.xml",
        "views/fiq_gui_control_admin.xml",
        "views/project_task_type_views.xml",
        "views/control_room_action.xml",
        "data/fiq_gui_control_flater.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Odoo 20-regel 30/31 (Gjermund 23.07): assets deklareres EKSPLISITT.
            # Wildcard skjuler lasterekkefolgen — og rekkefolgen mellom skall og flate
            # var nettopp det som felte grensesnittet 18.07. Stil, logikk, maler.
            "fiq_gui_control/static/src/control_room.scss",
            "fiq_gui_control/static/src/control_room.js",
            "fiq_gui_control/static/src/systray.js",
            "fiq_gui_control/static/src/control_room.xml",
            "fiq_gui_control/static/src/kr_lister.scss",
            "fiq_gui_control/static/src/kr_lister.js",
            "fiq_gui_control/static/src/kr_lister.xml",
        ],
    },
    "application": True,
    "installable": True,
}
