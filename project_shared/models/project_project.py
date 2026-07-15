from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    shared = fields.Boolean(
        string="Shared",
        compute="_compute_shared",
        store=True,
        help="Indicates whether the project is shared (has a follower who is not a regular user)."
    )

    @api.depends("message_partner_ids")
    def _compute_shared(self):
        for project in self:
            project.shared = any(
                not partner.user_ids or partner.user_ids.filtered(lambda u: u.share)
                for partner in project.message_partner_ids
            )
