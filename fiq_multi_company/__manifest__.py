# Copyright 2026 FIQ AS, Loym AS
# License OPL-1 (Odoo Proprietary License v1.0).
# Eid av FIQ AS. Kode utviklet av Loym AS eies av FIQ og kan brukes fritt av FIQ
# (Gjermund E. Waehre 23.07.2026).
{
    "name": "FIQ Multi-Company",
    "summary": "Per-firma scoping av CRM-stadier, tapsårsaker, e-postmaler og partnerkategorier",
    "description": """
Erstatter de OCA-modulene som mangler 19.0 (crm_stage_multi_company,
crm_lost_reason_multi_company, mail_template_multi_company,
partner_category_multi_company) med ÉN slank, 19-native FIQ-modul.

Legger et valgfritt company_id + global multi-company record-rule på:
- crm.stage          (per-firma salgstrinn)
- crm.lost.reason    (per-firma tapsårsaker)
- mail.template      (per-firma e-postmaler – egen signatur/logo)
- res.partner.category (per-firma partnerkategorier)

Tomt company_id = delt på tvers av alle selskaper (bevarer eksisterende
oppførsel). Satt company_id = synlig kun for det selskapet (+ delte).
""",
    "author": "FIQ as, Loym AS",
    "website": "https://www.fiq.no",
    "version": "19.0.1.0.2",
    "license": "OPL-1",
    "category": "Multi Company",
    "depends": ["crm", "mail"],
    "data": [
        "security/fiq_multi_company_rules.xml",
        "views/fiq_multi_company_views.xml",
    ],
    "installable": True,
}
