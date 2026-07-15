# Copyright 2025 Loym AS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.exceptions import UserError


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _unlink_or_archive(self, check_access=True):
        if len(self):
            raise UserError(
                "Add attribute value: Add only one value the first time.\n"
                "Delete attribute value: Not possible. (Well, delete"
                " the variant tag and the attribute tag from each product variant.)\n"
                "\n"
                "This method is not allowed to delete/archive product variants.\n"
                "If needed, delete or archive product variants manually.\n"
                f"Product variant ids: {self.ids}"
                )
