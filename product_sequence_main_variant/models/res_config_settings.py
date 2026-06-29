from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"
    
    product_template_sequence_number_from_main_variant = fields.Boolean(
        string="Get Product Template No. from Main Variant",
        config_parameter="product_sequence_main_variant.product_template_sequence_number_from_main_variant"
    )
