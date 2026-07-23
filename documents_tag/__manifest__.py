# Copyright 2025 Loym AS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Documents Tag",
    "summary": "",
    "author": "FIQ as, Loym AS, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/knowledge",
    "version": "19.0.5.1.6",
    "license": "AGPL-3",
    "depends": [
        "documents",
        "documents_form",
    ],
    "data": [
        "views/documents_document_views.xml",
        "views/documents_tag_views.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'documents_tag/static/src/css/kanban_tags.css',
        ],
    },
    "post_init_hook": "post_init_hook",
}
