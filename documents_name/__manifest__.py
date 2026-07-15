# Copyright 2025 Loym AS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "installable": False,  # 19: native name er flerspraaklig - pensjonert, ryddes av FIQ 18->19-migrasjonen
    "name": "Documents Name",
    "summary": "",
    "author": "FIQ as, Loym AS, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/knowledge",
    "version": "19.0.5.0.1",
    "license": "AGPL-3",
    "depends": ["documents", "documents_form"],
    "data": [
        "views/documents_document_views.xml",
    ],
    "post_init_hook": "post_init_hook",
}
