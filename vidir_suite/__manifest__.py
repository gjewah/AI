# -*- coding: utf-8 -*-
{
  "name": "Vidir Suite – CO₂-kalkulator & digitalt produktpass",
  "version": "19.0.5.0.0",
  "summary": "Klimaregnskap og digitalt produktpass (DPP): kalkulator, GS1/QR, portal, bransjeprofiler, ESG-eksport til Excel, ERP-mapping, flerspråklig.",
  "license": "LGPL-3",
  "author": "Vidir",
  "depends": [
    "base",
    "website",
    "portal",
    "product",
    "project"
  ],
  "data": [
    "security/ir.model.access.csv",
    "views/settings_views.xml",
    "views/co2_templates.xml",
    "views/dpp_landing_templates.xml",
    "views/portal_templates.xml",
    "views/dpp_report.xml",
    "views/dpp_report_multi.xml",
    "views/dpp_customer_report.xml",
    "views/jrc_import_wizard.xml",
    "views/dpp_form_views.xml",
    "views/dpp_actions.xml",
    "views/industry_views.xml",
    "views/export_map_views.xml"
  ],
  "assets": {
    "web.assets_frontend": [
      "/vidir_suite/static/src/scss/co2_calculator.scss",
      "/vidir_suite/static/src/js/co2_calculator.js"
    ]
  },
  "installable": True,
  "application": True,
}