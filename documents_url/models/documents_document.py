from odoo import models, fields, api

class DocumentsDocument(models.Model):
    _inherit = "documents.document"
    
    def action_document_link(self):
        """
        Go to the external URL of the folder/file.
        """
        if not self:
            return {}

        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.url,
            "target": "new",
        }

    @api.onchange("url")
    def _compute_name_and_preview(self):
        """
        If name exists, do not update name based on URL.
        """
        if len(self) == 1 and self.url and self.name:
            return
        else:
            return super()._compute_name_and_preview()

    @api.model_create_multi
    def create(self, vals_list):
        """
        If no url, a document (record with attachment) will get the url of the folder.
        """
        for vals in vals_list:
            if "attachment_id" in vals and "url" not in vals and "folder_id" in vals:
                folder = self.browse(vals["folder_id"])
                if folder and folder.url:
                    vals["url"] = folder.url
        return super().create(vals_list)
