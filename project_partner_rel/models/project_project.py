from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command


class ProjectProject(models.Model):
    _inherit = "project.project"

    partner_ids = fields.Many2many(
        "res.partner",
        relation="project_partner_rel",
        string="Related Contacts",
    )

    @api.model
    def default_get(self, fields):
        """Set partner_id as the default value for partner_ids."""
        res = super().default_get(fields)
        if res.get("partner_id") and "partner_ids" in fields and not res.get("partner_ids"):
            res["partner_ids"] = [Command.link(res["partner_id"])]
        return res

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """When partner_id changes, add it to partner_ids if it"s not already there."""
        if self.partner_id:
            if self.partner_id not in self.partner_ids:
                self.partner_ids = [Command.link(self.partner_id.id)]

    @api.constrains("partner_id")
    def _check_partner_inclusion(self):
        """Ensure that partner_id is always included in partner_ids."""
        for record in self:
            if record.partner_id and record.partner_id not in record.partner_ids:
                record.partner_ids = [Command.link(record.partner_id.id)]
                # raise ValidationError("The Customer must be included in the Related Contacts.")
