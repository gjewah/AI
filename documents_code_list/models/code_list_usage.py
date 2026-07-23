from odoo import fields, models

class CodeListUsage(models.Model):
    _inherit = "code.list.usage"

    resource_id = fields.Reference(
        selection_add=[
            ('documents.document', 'Document'),
        ],
    )
