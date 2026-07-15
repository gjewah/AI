from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    document_ids = fields.Many2many(
        "documents.document",
        compute="_compute_document_ids",
        # string="Documents", # use_documents in documents_project and documents_fsm
    )

    def _compute_document_ids(self):
        for project in self:
            project.document_ids = self.env["documents.document"].search([
                "|",
                "&", ("res_model", "=", "project.project"), ("res_id", "=", project.id),
                "&", ("res_model", "=", "project.task"), ("res_id", "in", project.task_ids.ids),
            ])
