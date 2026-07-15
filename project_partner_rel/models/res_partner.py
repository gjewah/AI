from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    project_ids = fields.Many2many(
        "project.project",
        relation="project_partner_rel",
        string="Related Projects",
    )

    project_count = fields.Integer(string="Project Count", compute='_compute_project_count', store=True)

    @api.depends('project_ids')
    def _compute_project_count(self):
        for partner in self:
            partner.project_count = len(partner.project_ids)
