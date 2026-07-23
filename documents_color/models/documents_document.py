from odoo import models, fields, api

class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    color = fields.Integer(string="Color Index", export_string_translation=False)
