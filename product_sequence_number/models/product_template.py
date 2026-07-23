from odoo import api, fields, models


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "sequence.number.mixin", "expression.value.mixin"]
    _sequence_field = "sequence_number"
    _ir_sequence_code = "product.template"

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
        string="Product Template No.",
        copy=False,
    )
