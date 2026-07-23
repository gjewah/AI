from odoo import models, fields


class ResUsersTag(models.Model):
    _name = "res.users.tag"
    _description = "User Tags"

    name = fields.Char(string="Name", required=True)

    def action_open_tags(self):
        action = self.env.ref("base.tag_window_action").read()[0]

        action["context"] = dict(self.env.context, **{
            "search_default_my_tags": 1,
            "user_tag_ids": self.env.user.tag_ids.ids,
        })

        return action
