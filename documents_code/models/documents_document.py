from odoo import models, fields, api
from odoo.addons.base_display_name.models.expression_value_mixin import ExpressionValueMixin


class DocumentsDocument(models.Model):
    _name = "documents.document"
    _inherit = ["documents.document", "expression.value.mixin"]
    _unique_sequence = models.Constraint(
        "UNIQUE(code, company_id)",
        "code must be unique per company!",
    )

    company_code = fields.Char(
        related="company_id.code",
        string="Company Code",
        store=True,
        readonly=True,
    )
    code = fields.Char(
        string="Code",
        help="Internal code to identify the document or folder",
        copy=False,
    )

    # Since Odoo has a custom _compute_display_name() for documents,
    # user-defined display_name cannot rely on expression.value.mixin alone.

    @api.model
    def _search_display_name(self, operator, value):
        return ExpressionValueMixin._search_display_name(self, operator, value)

    @api.depends(lambda self: self.get_valid_field_paths_from_source("ir.model", "display_name_expression"))
    def _compute_display_name(self):
        return ExpressionValueMixin._compute_display_name(self)
