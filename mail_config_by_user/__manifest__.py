# Copyright 2025 Loym AS
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Mail Config By User",
    "author": "Loym AS, Odoo Community Association (OCA)",
    "website": "https://loym.com",
    "version": "19.0.5.0.0",
    "license": "AGPL-3",
    "depends": [
        "mail",
    ],
    "data": [
        "security/ir_mail_server_security.xml",
        "security/ir.model.access.csv",
        "views/res_users_views.xml",
    ],
}
