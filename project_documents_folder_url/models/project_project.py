from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    documents_folder_url = fields.Char(
        string="External URL",
        related="documents_folder_id.url",
        readonly=False,
    )
