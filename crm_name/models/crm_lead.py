from odoo import api, fields, models


class CrmLead(models.Model):
    _name = "crm.lead"
    _inherit = [
        "crm.lead",
        "expression.value.mixin",
    ]

    partner_short_name = fields.Char(
        related="partner_id.short_name",
        string="Short Name",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._compute_name()
        return records

    def write(self, vals):
        super().write(vals)
        if "name" not in vals:
            self._compute_name()
        return True

    @api.depends("write_date", "partner_id.name", "partner_id.short_name")
    def _compute_name(self):
        for lead in self:
            lead.name = False
            lead.name = lead.get_value_from_source(
                "ir.config_parameter", "crm_name.crm_lead_name_expression"
            )
            if lead.name.startswith("NewId"):
                lead.name = "New"
