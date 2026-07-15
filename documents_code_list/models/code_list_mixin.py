# Copyright 2026 FIQ
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class CodeListMixin(models.AbstractModel):
    _inherit = "code.list.mixin"

    def _get_document_vals(self, attachment):
        """
        When creating a document from another record, include the code list usage.
        """
        vals = super()._get_document_vals(attachment)
        if self.code_list_usage_ids:
            vals["code_list_usage_ids"] = [
                (0, 0, {
                    # Link to the new document
                    "model": "documents.document",
                    "res_id": attachment.id,
                    "code_list_item_id": usage.code_list_item_id.id,
                    "code_list_id": usage.code_list_id.id,
                })
                for usage in self.code_list_usage_ids
            ]
        return vals
