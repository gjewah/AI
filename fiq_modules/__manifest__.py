# Copyright 2025 FIQ as
# License OPL-1 (Odoo Proprietary License v1.0).
# Eid av FIQ AS. Kode utviklet av Loym AS eies av FIQ og kan brukes fritt av FIQ
# (Gjermund E. Waehre 23.07.2026).

{
    "name": "FIQ modules",
    "summary": "",
    "author": "FIQ as",
    "data": [
        "views/ir_sequence_views.xml",
        "views/res_partner_views.xml",
    ],
    "depends": [
        "base_fiq",
        "crm_fiq",
        "documents_fiq",
        "mail_fiq",
        "product_fiq",
        "project_fiq",
    ],
    "license": "OPL-1",
    "version": "19.0.5.0.2",
    "website": "https://www.loym.com",
}
