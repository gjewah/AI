from odoo import models, fields


class Partner(models.Model):
    _inherit = "res.partner"

    def action_see_documents(self):
        action = super().action_see_documents()
        list_view_id = self.env.ref("documents.documents_view_list").id
        kanban_view_id = self.env.ref('documents.document_view_kanban').id
        action["views"] = [(list_view_id, "list"), (kanban_view_id, "kanban")]
        return action
