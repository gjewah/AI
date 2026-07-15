from odoo import api, fields, models


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["code.list.mixin", "project.task", ]
