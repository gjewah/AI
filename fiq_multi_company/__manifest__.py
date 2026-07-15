# Copyright 2026 FIQ AS, Loym AS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
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
    "version": "19.0.1.0.0",
    "license": "AGPL-3",
    "category": "Multi Company",
    "depends": ["crm", "mail"],
    "data": [
        "security/fiq_multi_company_rules.xml",
        "views/fiq_multi_company_views.xml",
    ],
    "installable": True,
}
