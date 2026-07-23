from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    project_document_ids = fields.Many2many(
        "documents.document",
        compute="_compute_project_document_ids",
        string="Project Documents",
    )

    def _compute_project_document_ids(self):
        for partner in self:
            partner.project_document_ids = partner.project_ids.document_ids
