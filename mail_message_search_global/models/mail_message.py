from odoo import api, models


class MailMessage(models.AbstractModel):
    _inherit = "mail.message"

    def action_open_related(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Related Record",
            "res_model": self.model,
            "view_mode": "form",
            "res_id": self.res_id,
            "target": "current",
        }
