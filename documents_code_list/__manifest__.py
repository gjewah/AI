# Copyright FIQ
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Documents Code Lists",
    "version": "19.0.1.0.1",
    "category": "Tools",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "author": "FIQ, Odoo Community Association (OCA)",
    "maintainers": ["norlinhenrik"],
    "website": "https://github.com/OCA/community-data-files",
    "depends": ["documents_form", "base_code_list"],
    "data": [
        "data/ir_actions_server_data.xml",
        "views/documents_document_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
