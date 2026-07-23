# Copyright 2026 FIQ as
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Mail Chat",
    "author": "FIQ as, Odoo Community Association (OCA)",
    "website": "https://fiq.no",
    "version": "19.0.1.0.0",
    "license": "AGPL-3",
    "depends": [
        "mail",
        "web",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/record_rules.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_chat/static/src/js/mail_chat.js",
            "mail_chat/static/src/xml/mail_chat.xml",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
}
