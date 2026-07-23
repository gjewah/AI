# Copyright 2025 Loym AS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Mail never autofollow",
    "summary": """
        Never automatically add new recipients as followers
        on mail.compose.message""",
    "author": "Loym AS," "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/mail",
    "category": "Social Network",
    "version": "19.0.5.0.0",
    "license": "AGPL-3",
    "depends": ["mail"],
    "installable": True,
    "excludes": ["mail_optional_autofollow"],
}
