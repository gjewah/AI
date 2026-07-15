from odoo import models, fields, api

class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    name_translate = fields.Char(
        string="Name.",
        translate=True,
    )

    # TODO: New module base_new_field_translate with mixin to handle this
    # Use a new field name_translate or in-place update name field (needs uninstall hook)?

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals = self._set_name_or_name_translate_in_vals(vals)
        records = super().create(vals_list)
        # If name is not in vals, it is computed.
        records._set_name_or_name_translate()
        return records
    
    def write(self, vals):
        vals = self._set_name_or_name_translate_in_vals(vals)
        super().write(vals)
        # If name is not in vals, it is computed.
        self._set_name_or_name_translate()
        return True
    
    def _set_name_or_name_translate_in_vals(self, vals):
        if "name_translate" in vals:
            vals["name"] = vals["name_translate"]
        elif "name" in vals:
            vals["name_translate"] = vals["name"]
        return vals

    def _set_name_or_name_translate(self):
        for record in self:
            if not record.name_translate and record.name:
                record.name_translate = record.name
            elif not record.name and record.name_translate:
                record.name = record.name_translate
