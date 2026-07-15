from odoo import models, fields

PROJECT_TASK_READABLE_FIELDS = {
    "code",
}

PROJECT_TASK_WRITABLE_FIELDS = {
    "code",
}


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["project.task", "sequence.number.mixin", "expression.value.mixin"]
    _sequence_field = "code" # Same as in OCA project_task_code
    _ir_sequence_code = "project.task"

    _unique_sequence = models.Constraint(
        "UNIQUE(code, company_id)",
        "code must be unique per company!",
    )
    @property
    def TASK_PORTAL_READABLE_FIELDS(self):
        return super().TASK_PORTAL_READABLE_FIELDS | PROJECT_TASK_READABLE_FIELDS

    @property
    def TASK_PORTAL_WRITABLE_FIELDS(self):
        return super().TASK_PORTAL_WRITABLE_FIELDS | PROJECT_TASK_WRITABLE_FIELDS

    company_code = fields.Char(
        related="company_id.code",
        string="Company Code",
        store=True,
        readonly=True,
    )
    code = fields.Char(
        string="Task No.",
        # required=True,
        # default="/",
        copy=False,
    )
