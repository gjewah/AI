from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_open_res_partner_code_list(self):
        action = self.env.ref(
            "contacts.action_contacts"
        ).read()[0]

        action["context"] = dict(self.env.context, **{
            "search_default_my_tags": 1,
            "user_tag_ids": self.env.user.tag_ids.ids,
        })

        return action
