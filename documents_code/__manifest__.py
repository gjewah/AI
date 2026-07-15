# Copyright 2025 Loym AS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Documents Code",
    "summary": "",
    "author": "FIQ, Loym",
    "website": "https://github.com/OCA/knowledge",
    "version": "19.0.1.0.4",
    "license": "AGPL-3",
    "depends": [
        "base_display_name",
        "documents",
        "documents_form",
        "res_company_code",
    ],
    "data": [
        "views/documents_document_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "pre_uninstall_hook",
}
