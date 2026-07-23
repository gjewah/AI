from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.fields import Command


class DocumentsTag(models.Model):
    _inherit = "documents.tag"
    _order = "name"

    tooltip_translate = fields.Char(
        string="Tooltip.",
        translate=True,
    )
    parent_id = fields.Many2one(
        "documents.tag",
        compute="_compute_parent_id",
        store=True,
    )
    parent_ids = fields.Many2many(
        'documents.tag',
        'documents_tag_hierarchy_rel',
        'child_id',
        'parent_id',
        string="Parent Tags"
    )
    child_ids = fields.Many2many(
        'documents.tag',
        'documents_tag_hierarchy_rel',
        'parent_id',
        'child_id',
        string="Children Tags"
    )
    all_child_ids = fields.Many2many(
        'documents.tag',
        compute='_compute_all_child_ids',
        string="All Children",
    )

    # TODO: Create a translate mixin based on documents_name/models/documents_document.py

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals = self._set_tooltip_or_tooltip_translate(vals)
        return super().create(vals_list)
    
    def write(self, vals):
        vals = self._set_tooltip_or_tooltip_translate(vals)
        return super().write(vals)
    
    def _set_tooltip_or_tooltip_translate(self, vals):
        if "tooltip_translate" in vals:
            vals["tooltip"] = vals["tooltip_translate"]
        elif "tooltip" in vals:
            vals["tooltip_translate"] = vals["tooltip"]
        return vals

    @api.depends('parent_ids')
    def _compute_parent_id(self):
        for tag in self:
            if len(tag.parent_ids) == 1:
                tag.parent_id = tag.parent_ids[0]
            else:
                tag.parent_id = False

    def _compute_all_child_ids(self):
        for tag in self:
            if not tag.id:
                tag.all_child_ids = self.env['documents.tag']
                continue

            query = """
                WITH RECURSIVE descendants AS (
                    SELECT child_id
                    FROM documents_tag_hierarchy_rel
                    WHERE parent_id = %s
                    UNION
                    SELECT r.child_id
                    FROM documents_tag_hierarchy_rel r
                    JOIN descendants d ON r.parent_id = d.child_id
                )
                SELECT child_id FROM descendants;
            """
            self.env.cr.execute(query, (tag.id,))
            child_ids = [row[0] for row in self.env.cr.fetchall()]
            tag.all_child_ids = (
                self.env['documents.tag']
                .browse(child_ids)
                .sorted(key=lambda t: t.name)
            )

    @api.constrains('parent_ids', 'child_ids')
    def _check_self_reference(self):
        for tag in self:
            if tag in tag.parent_ids:
                raise ValidationError(f"The tag '{tag.name}' cannot be its own parent or child.")

    def action_open_tag_selector(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Document Tags',
            'res_model': 'documents.tag',
            'view_mode': 'list',
            'view_id': self.env.ref('documents_tag.view_documents_tag_list_select').id,
            'target': 'new',
            'context': {
                'active_id': self.id,
                'model_name': self._name,
                'field_name': "documents_tag_ids",
            },
        }

    def add_selected_tags(self):
        """
        Called from the header button in the selectable tree view.
        Context must include:
            - active_id: the ID of the original record
            - field_name: the Many2many field to update
            - model_name: the model of the original record
        """
        original_model_name = self._context.get('model_name')
        original_record_id = self._context.get('active_id')
        field_name = self._context.get('field_name')

        if not (original_model_name and original_record_id and field_name):
            raise ValidationError("Missing context keys for adding selected tags.")

        original_record = self.env[original_model_name].browse(original_record_id)
        if not original_record.exists():
            raise ValidationError("Original record not found.")

        # Exclude self if original record is a documents.tag to prevent self-reference
        if original_model_name == 'documents.tag':
            selected_tags = self.filtered(lambda t: t.id != original_record_id)
        else:
            selected_tags = self

        # Use Command.link to link each selected tag
        original_record.write({field_name: [Command.link(tag.id) for tag in selected_tags]})
