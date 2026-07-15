# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

import psycopg2

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class SequenceNumberMixin(models.AbstractModel):
    _name = "sequence.number.mixin"
    _description = "Sequence No. Mixin"

    # Required settings by the model inheriting the mixin
    _sequence_field = "sequence_number"
    _ir_sequence_code = None  # Recommended: model name

    @api.model_create_multi
    def create(self, vals_list):
        """Set sequence_number and name, if sequence_number is not set."""
        vals_list_ok = [vals for vals in vals_list if vals.get(self._sequence_field)]
        vals_list_todo = [vals for vals in vals_list if not vals.get(self._sequence_field)]
        # Create first, so we can use the record "id" etc. in the expression
        records_ok = super().create(vals_list_ok)
        records_todo = super().create(vals_list_todo)
        records_todo.set_sequence_field_and_name()
        return records_ok | records_todo

    def write(self, vals):
        super().write(vals)
        self._set_name_if_empty()
        return True

    def set_sequence_field_and_name(self):
        self._set_sequence_field()
        self._set_name_if_empty()

    def _set_sequence_field(self):
        records = self.filtered(lambda r: not r[r._sequence_field])
        for rec in records:
            rec[self._sequence_field] = self.env['ir.sequence'].next_by_code(self._ir_sequence_code)

    def _set_name_if_empty(self):
        """Set name = sequence_number if removing name or no existing name

        Checking if the record has a name may affect the performance..."""

        # Relevant for uninstalling the module
        context = self.env.context
        if "prefetch_fields" in context and not context.get("prefetch_fields"):
            return

        if "name" not in self._fields:
            return

        for rec in self:
            if rec[rec._sequence_field] and not rec.name:
                rec.name = rec[rec._sequence_field]
