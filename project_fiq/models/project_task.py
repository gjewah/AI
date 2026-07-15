from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    user_ids = fields.Many2many(
        domain="[('active', '=', True)]",
    )
