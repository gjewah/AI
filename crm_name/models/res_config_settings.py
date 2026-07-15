from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    crm_lead_name_expression = fields.Char(
        config_parameter="crm_name.crm_lead_name_expression",
        readonly=False,
        string="Lead Name Pattern",
    )

    @api.constrains("crm_lead_name_expression")
    def _check_crm_lead_name_expression_and_triggers(self):
        self.env["crm.lead"].raise_error_if_invalid_expression(
            self.crm_lead_name_expression
        )
