from urllib.parse import urlencode

from odoo import models


class ActionGotoDocumentsMixin(models.AbstractModel):
    _name = "action.goto.documents.mixin"
    _description = "Action Goto Documents Mixin"

    def action_goto_documents(self):
        self.ensure_one()
        contact_type = self.env.context.get("contact_type")
        internal_external = self.env.context.get("internal_external")
        folder = getattr(self, contact_type + "_folder_id")
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
