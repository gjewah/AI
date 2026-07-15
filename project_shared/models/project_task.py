from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    shared_project = fields.Boolean(
        related="project_id.shared",
        string="Shared Project",
    )
    shared = fields.Boolean(
        string="Shared",
        compute="_compute_shared",
        store=True,
        help="Indicates whether the task is shared (has a follower who is not a regular user)."
    )

    @api.depends("message_partner_ids")
    def _compute_shared(self):
        for task in self:
            task.shared = any(
                not partner.user_ids or partner.user_ids.filtered(lambda u: u.share)
                for partner in task.message_partner_ids
            )

    def action_open_share_project_wizard(self):
        self.ensure_one()
        return self.project_id.action_open_share_project_wizard()
