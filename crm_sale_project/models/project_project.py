from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProjectProject(models.Model):
    _inherit = "project.project"

    is_customer_project = fields.Boolean(
        string="Is Customer Project",
        help="Indicates if the project is for a customer.",
    )
