from odoo import api, fields, models


class CrmLead(models.Model):
    _name = "crm.lead"
    _inherit = ["crm.lead", "documents.tag.mixin"]

    # def _get_document_vals(self, attachment):
    #     vals = super()._get_document_vals(attachment)
    #     if self.documents_tag_id:
    #         vals["documents_tag_id"] = self.documents_tag_id.id
    #     return vals
