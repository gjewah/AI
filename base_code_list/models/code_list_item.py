from odoo import api, exceptions, fields, models


class CodeListItem(models.Model):
    _name = "code.list.item"
    _description = "Code List Item"
    _order = "list_id, code, name"
    _rec_name = "display_name"

    # I GET ERROR WHEN I REORDER THE TOP LEVEL ITEMS OF A LIST.
    # _unique_code = models.Constraint(
    #     "UNIQUE(code, list_id)",
    #     "code must be unique per list!",
    # )
    # @api.constrains("code", "list_id")
    # def _check_unique_code_per_list(self):
    #     for record in self:
    #         if not record.code or not record.list_id:
    #             continue
    #         duplicate_count = self.search_count([
    #             ("id", "!=", record.id),
    #             ("list_id", "=", record.list_id.id),
    #             ("code", "=", record.code),
    #         ])
    #         if duplicate_count:
    #             raise exceptions.ValidationError("code must be unique per list!")

    @api.depends("code", "name", "list_id.code", "list_id.name")
    def _compute_display_name(self):
        for r in self:
            r.display_name = f"{r.list_id.code or r.list_id.name}: {r.code or ''} {r.name}"

    @api.constrains("list_id", "parent_id", "sequence")
    def _check_max_9_items_per_level_without_separator(self):
        level_keys = set()
        for record in self:
            if not record.list_id or not record.list_id.compute_item_codes:
                continue
            if record.list_id.sequence_separator:
                continue

            level_keys.add((record.list_id.id, record.parent_id.id if record.parent_id else False))
            if record.sequence and record.sequence > 9:
                raise exceptions.ValidationError(
                    "With Compute Code enabled and empty Sequence Separator, a level supports maximum 9 items."
                )

        for list_id, parent_id in level_keys:
            if self.search_count([
                ("list_id", "=", list_id),
                ("parent_id", "=", parent_id),
            ]) > 9:
                raise exceptions.ValidationError(
                    "With Compute Code enabled and empty Sequence Separator, a level supports maximum 9 items."
                )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )
    code = fields.Char(
        string="Code",
        compute="_compute_code",
        store=True,
        readonly=False,
        required=False,
        copy=False,
    )
    compute_item_codes = fields.Boolean(
        related="list_id.compute_item_codes",
        readonly=True,
    )
    name = fields.Char(required=True, copy=False, translate=True)
    description = fields.Text(translate=True)
    list_id = fields.Many2one(
        "code.list",
        string="Code List",
        required=True,
        ondelete="restrict",
    )
    parent_id = fields.Many2one(
        "code.list.item",
        string="Parent Item",
        ondelete="restrict",
    )
    parent_path = fields.Char(
        index=True,
        copy=False,
    )
    child_ids = fields.One2many(
        comodel_name='code.list.item',
        inverse_name='parent_id',
        string='Child Items',
        compute='_compute_child_ids', # to reorder only sibling items
        readonly=False,
        store=True,
    )

    @api.depends("parent_id", "sequence")
    def _compute_child_ids(self):
        for record in self:
            record.child_ids = self.search([('parent_id', '=', record.id)])

    child_list_id = fields.Many2one(
        "code.list",
        string="Child Code List",
        ondelete="restrict",
    )
    active = fields.Boolean(default=True)
    list_parent_ids = fields.Many2many(
        related="list_id.parent_ids",
        string="List used by items of",
        readonly=True,
    )
    sequence = fields.Integer()
    sequence_separator = fields.Char(
        string="Sequence Separator",
        related="list_id.sequence_separator",
        readonly=True,
        help="Separator used to build the sequence code for items in this list.",
    )
    user_tag_ids = fields.Many2many(
        "res.users.tag",
        string="User Tags"
    )

    def action_open_items_to_reorder(self):
        self.ensure_one()
        return {
            "name": f"Reorder Items of {self.display_name}",
            "type": "ir.actions.act_window",
            "res_model": "code.list.item",
            "view_mode": "list,form",
            "domain": [("list_id", "=", self.list_id.id), ("parent_id", "=", self.id)],
            "context": {
                "default_list_id": self.list_id.id,
                "default_parent_id": self.id,
                "reorder_items": True,
                "list_view_ref": "base_code_list.code_list_item_view_list_reorder",
            },
        }

    @api.depends("parent_id", "sequence", "sequence_separator", "list_id.compute_item_codes")
    def _compute_code(self):
        """
        Compute code based on parent and sequence if compute_item_codes is True:
        - Top level: 1, 2, 3 ...
        - Child: 1.1, 1.2, 2.1 ...
        - Supports multiple levels: 1.1.1, 1.1.1.1, etc.
        - Separator is defined by the sequence_separator field in the related list_id
        """
        for item in self:
            if item.list_id.compute_item_codes:
                separator = item.sequence_separator or ""
                sequence_parts = []
                current_item = item

                # Traverse up the hierarchy to build the full sequence code
                while current_item:
                    sequence_parts.append(str(current_item.sequence))
                    current_item = current_item.parent_id

                # Reverse the parts to get the correct order and join with the separator
                item.code = separator.join(reversed(sequence_parts))
            else:
                # Do not delete the code if compute_item_codes is False
                item.code = item.code or False

    # --- Auto-set sequence ved create for nye items ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'sequence' not in vals or not vals['sequence']:
                parent_id = vals.get('parent_id')
                list_id = vals.get('list_id')
                if list_id:
                    # Find the max sequence within the same parent
                    max_seq = (
                        self.search([
                            ('list_id', '=', list_id),
                            ('parent_id', '=', parent_id),
                        ], order='sequence desc', limit=1).sequence
                        or 0
                    )
                    vals['sequence'] = max_seq + 1  # Increment by 1 for new sequence
        return super().create(vals_list)

    def write(self, vals):
        """
        Update sequence and code if parent_id or sequence changes.
        If parent_id changes, reassign sequence and update old parent's children.
        """
        for record in self:
            old_parent_id = record.parent_id
            new_parent_id = vals.get('parent_id', old_parent_id.id if old_parent_id else False)

            if new_parent_id and new_parent_id != old_parent_id.id:
                list_id = vals.get('list_id', record.list_id.id)
                if self.env['code.list'].browse(list_id).compute_item_codes:
                    # Reassign sequence for the new parent
                    max_seq = (
                        self.search([
                            ('list_id', '=', list_id),
                            ('parent_id', '=', new_parent_id),
                        ], order='sequence desc', limit=1).sequence
                        or 0
                    )
                    vals['sequence'] = max_seq + 1

                    # Recompute sequence for old parent's children
                    if old_parent_id:
                        siblings = self.search([
                            ('list_id', '=', list_id),
                            ('parent_id', '=', old_parent_id.id),
                        ], order='sequence')
                        for idx, sibling in enumerate(siblings, start=1):
                            sibling.sequence = idx

        res = super().write(vals)

        # Recompute code for all affected records
        if 'parent_id' in vals or 'sequence' in vals:
            self._recompute_item_codes()

        return res

    def _recompute_item_codes(self):
        """
        Recompute sequence codes for all items in the hierarchy if compute_item_codes is True.
        """
        for item in self:
            if item.list_id.compute_item_codes:
                item._compute_code()
                for child in item.child_ids:
                    child._recompute_item_codes()
