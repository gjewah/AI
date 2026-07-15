from urllib.parse import urlencode

from odoo import api, fields, models, Command


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["project.task", "documents.tag.mixin"]

    def _get_document_vals(self, attachment):
        vals = super()._get_document_vals(attachment)
        # Main tag
        if self.documents_tag_id:
            vals["documents_tag_id"] = self.documents_tag_id.id
        elif self.project_id.documents_tag_id:
            vals["documents_tag_id"] = self.project_id.documents_tag_id.id
        # Tags
        if self.documents_tag_ids:
            vals['tag_ids'] = [
                Command.link(tag.id)
                for tag in self.documents_tag_ids
            ]
        # else use project default tags
        return vals
