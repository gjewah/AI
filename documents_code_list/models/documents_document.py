from odoo import api, fields, models

class DocumentsDocument(models.Model):
    _name = "documents.document"
    _inherit = ["code.list.mixin", "documents.document"]
