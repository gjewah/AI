from odoo import api, fields, models


class ProjectProject(models.Model):
    _name = "project.project"
    _inherit = [
        "project.project",
        "expression.value.mixin",
    ]

    internal_external = fields.Selection(
        string="Internal/External",
        selection=[("i", "Internal"), ("e", "External")],
        copy=True,
    )
    sequence_sequence = fields.Char(
        help="Value from ir.sequence",
        copy=False,
    )

    # @api.constrains("company_id", "internal_external")
    # def set_sequence_code(self):
    #     # Set sequence_code based on sequence_sequence
    #     for rec in self:
    #         if not rec.sequence_sequence:
    #             if rec.sequence_code:
    #                 rec.sequence_sequence = rec.sequence_code
    #             else:
    #                 rec.sequence_sequence = self.env["ir.sequence"].next_by_code(
    #                     "project.sequence"
    #                 )
    #         rec.sequence_code = rec.get_value_from_source(
    #             "ir.config_parameter", "project_internal_external.project_sequence_pattern"
    #         )

    # def write(self, vals):
    #     if "sequence_code" in vals and not vals.get("sequence_code"):
    #         vals["sequence_sequence"] = None
    #     if "sequence_sequence" in vals and not vals.get("sequence_sequence"):
    #         vals["sequence_code"] = None

    #     super().write(vals)

    #     if vals.get("sequence_code") or vals.get("sequence_sequence"):
    #         if not self.env.context.get("skip_sequence_constrains"):
    #             self.with_context(skip_sequence_constrains=True).set_sequence_code()
    #     return True
