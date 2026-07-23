from odoo import api, fields, models


class ProjectProject(models.Model):
    _name = 'project.project'
    _inherit = ['project.project', 'documents.mixin']
