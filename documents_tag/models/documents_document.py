from odoo import models, fields, api

class DocumentsDocument(models.Model):
    _name = "documents.document"
    _inherit = ["documents.document", "documents.tag.mixin"]

    documents_tag_ids = fields.Many2many(
        'documents.tag',
        related='tag_ids',
        readonly=False,
    )
    documents_tag_color = fields.Integer(string="Tag Color Index", related="documents_tag_id.color")
