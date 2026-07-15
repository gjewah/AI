from odoo import api, fields, models

Command = fields.Command


class ProductProduct(models.Model):
    _name = "product.product"
    _inherit = ["product.product", "documents.tag.mixin"]

    def _get_document_vals(self, attachment):
        vals = super()._get_document_vals(attachment)
        if self.documents_tag_id:
            vals["documents_tag_id"] = self.documents_tag_id.id
        if self.documents_tag_ids:
            vals["documents_tag_ids"] = [
                Command.link(tag_id) for tag_id in self.documents_tag_ids.ids
            ]
        return vals
