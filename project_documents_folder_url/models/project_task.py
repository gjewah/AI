from urllib.parse import urlencode

from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    project_documents_folder_url = fields.Char(
        string="Project URL",
        related="project_id.documents_folder_id.url",
    )

    def action_goto_documents(self):
        self.ensure_one()
        internal_external = self.env.context.get("internal_external")
        folder = self.project_id.documents_folder_id
        if internal_external == "internal":
            domain = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            params = {
                'action': self.env.ref("documents.document_action").id,
                'menu_id': self.env.ref("documents.menu_root").id,
                'model': 'documents.document',
                'documents_init_folder_id': folder.id
            }
            url = f"{domain}/web#{urlencode(params)}"
        else:
            url = folder.url
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }
