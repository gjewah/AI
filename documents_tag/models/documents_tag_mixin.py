from odoo import fields, models, Command
from odoo.exceptions import ValidationError


class DocumentsTagMixin(models.AbstractModel):
    _name = "documents.tag.mixin"
    _description = "documents.tag.mixin"

    documents_tag_id = fields.Many2one(
        comodel_name="documents.tag",
        string="DOC Main Tag",
        help="Set this tag on new and existing documents",
    )
    documents_tag_tooltip_translate = fields.Char(
        string="Tag Tooltip",
        related="documents_tag_id.tooltip_translate",
    )
    documents_tag_all_child_ids = fields.Many2many(
        'documents.tag',
        related="documents_tag_id.all_child_ids",
        string="DOC All Children",
    )
    documents_tag_ids_filter = fields.Boolean(
        string="DOC Tags Filter",
        default=True,
    )
    documents_tag_ids = fields.Many2many(
        comodel_name="documents.tag",
        string="DOC Tags",
        help="Add these tags to new and existing documents",
    )

    def _compute_documents_tag_ids_filter(self):
        self.documents_tag_ids_filter = True

    def _get_document_vals(self, attachment):
        vals = super()._get_document_vals(attachment)
        if self.documents_tag_id:
            vals["documents_tag_id"] = self.documents_tag_id.id
        return vals

    def write(self, vals):
        res = super().write(vals)

        tag_main_changed = "documents_tag_id" in vals
        tag_multi_changed = "documents_tag_ids" in vals

        if not (tag_main_changed or tag_multi_changed):
            return res

        # Related documents
        documents = self.env["documents.document"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "in", self.ids),
            ]
        )
        if not documents:
            return res

        # === 1. Handle main tag (Many2one) ===
        if tag_main_changed:
            documents.documents_tag_id = self.documents_tag_id.id

        # === 2. Handle secondary tags (Many2many) ===
        if tag_multi_changed:
            documents.documents_tag_ids = [
                Command.link(tag.id) for tag in self.documents_tag_ids
            ]

        return res

    def action_open_tag_selector(self):
        if self.documents_tag_ids_filter:
            domain = [('id', 'in', self.documents_tag_all_child_ids.ids)]
        else:
            domain = []
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Document Tags',
            'res_model': 'documents.tag',
            'view_mode': 'list',
            'view_id': self.env.ref('documents_tag.view_documents_tag_list_select').id,
            'target': 'new',
            'domain': domain,
            'context': {
                'active_id': self.id,
                'model_name': self._name,
                'field_name': "documents_tag_ids",
            },
        }
