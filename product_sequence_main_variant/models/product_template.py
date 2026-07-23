# Copyright (C) 2023 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).


from odoo import api, fields, models


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "sequence.number.mixin"]

    main_variant_id = fields.Many2one(
        comodel_name="product.product",
        string="Main Variant",
        # group="stock.group_stock_manager",
        help="The main variant of the product template. "
             "This is used to determine the unique code for the product template. "
             "Only PRODUCT MANAGER can change this value.",
    )
    use_main_variant_sequence = fields.Boolean(
        string="Use Main Variant Sequence",
        compute="_compute_use_main_variant_sequence",
    )
    sequence_number = fields.Char(
        string="Product Number",
        compute="_compute_sequence_number",
        store=True,
    )

    @api.depends()
    def _compute_use_main_variant_sequence(self):
        is_enabled = self.env['ir.config_parameter'].sudo().get_param(
            'product_sequence_main_variant.product_template_sequence_number_from_main_variant', 
            default=False
        )
        self.use_main_variant_sequence = is_enabled

    @api.depends(
        "product_variant_ids.sequence_number",
        "product_variant_ids.active",
        "main_variant_id",
    )
    def _compute_sequence_number(self):
        """Get active product variant sequence_number."""
        for template in self:
            if template.use_main_variant_sequence and template.main_variant_id:
                template.sequence_number = template.main_variant_id.sequence_number
