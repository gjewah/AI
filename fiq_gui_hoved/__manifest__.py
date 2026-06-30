# -*- coding: utf-8 -*-
{
    "name": "FIQ Hovedmeny",
    "version": "19.0.2.0.0",
    "summary": "Hovedmeny – dashbord/landingsside (OWL) med svartgrå sidemeny, "
               "per-firma aksent/logo, KPI-er fra Odoo-data og dynamisk vis/skjul av widgets.",
    "description": """
FIQ Hovedmeny
===================
Generisk dashbord-/landingsside som klient-handling (OWL), per FIQ-konvensjon:
 * Svartgrå (#1f2228) sidemeny – standard for alle firma; kun aksentfargen varierer per firma.
 * Per-firma branding: aksentfarge + logo settes på res.company.
 * KPI-rad + prosjektoversikt hentet fra ekte Odoo-data (project).
 * Dynamisk vis/skjul av panel-elementer (snippet-stil), lagret per bruker (nettleser).
 * Bygd generisk + togglebart; deler kjerne med en kommende portal-løsning (se controllers/portal.py).
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    "depends": ["web", "project"],
    "data": [
        "security/fiq_gui_hoved_groups.xml",
        "security/ir.model.access.csv",
        "views/res_company_views.xml",
        "views/fiq_gui_hoved_admin.xml",
        "views/hovedmeny_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_hoved/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
