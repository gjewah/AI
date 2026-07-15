from odoo import models, fields


class ResUsers(models.Model):
    _inherit = "res.users"

    # "Tags" name conflicts with "category_id" field in "res.partner" model, so we use "User Tags" instead.
    tag_ids = fields.Many2many("res.users.tag", string="User Tags")
