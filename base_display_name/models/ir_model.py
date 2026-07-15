# -*- coding: utf-8 -*-

import logging
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class IrModel(models.Model):
    _name = "ir.model"
    _inherit = ["ir.model", "expression.value.mixin"]

    use_display_name_expression = fields.Boolean(
        string="Use Display Name Expression",
        help=(
            "Use Display Name Expression only if:\n"
            "1. The model does inherit 'expression.value.mixin' in a module.\n"
            "2. The model does not inherit _compute_display_name() in any module."
            "   (See in 'partner_sequence_number' how to work around this.)"
        ),
    )

    display_name_expression = fields.Char(
        string="Display Name Exp.",
        help=(
            "Example: '{r.pick('parent_id.sequence_number')} {r.name}'\n"
            "Use python string format syntax.\n\n"
            "pick('field.path') will show the field value on these conditions:\n"
            "1. The value is non-false.\n"
            "2. The value is different from the record's name."
        ),
    )

    @api.constrains("display_name_expression")
    def raise_error_if_invalid_field_paths(self):
        return self.env[self.model].raise_error_if_invalid_expression(
            self.display_name_expression
        )
