from odoo import api, fields, models
from odoo.addons.base_display_name.models.expression_value_mixin import ExpressionValueMixin


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "sequence.number.mixin", "expression.value.mixin"]
    _sequence_field = "sequence_number"
    _ir_sequence_code = "res.partner"

    _unique_sequence = models.Constraint(
        "UNIQUE(sequence_number, company_id)",
        "sequence_number must be unique per company!",
    )

    company_code = fields.Char(
        related="company_id.code",
        string="Company Code",
        store=True,
        readonly=True,
    )
    sequence_number = fields.Char(
        string="Contact No.",
        copy=False,
    )

    # Since Odoo has a custom _compute_display_name() for contacts,
    # user-defined display_name cannot rely on expression.value.mixin alone.

    @api.model
    def _search_display_name(self, operator, value):
        return ExpressionValueMixin._search_display_name(self, operator, value)

    @api.depends(lambda self: self.get_valid_field_paths_from_source("ir.model", "display_name_expression"))
    def _compute_display_name(self):
        return ExpressionValueMixin._compute_display_name(self)
