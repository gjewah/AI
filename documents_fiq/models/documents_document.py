from odoo import models, fields


class DocumentsDocument(models.Model):
    _inherit = "documents.document"
    _order = "name" # not working
