# Copyright 2026 FIQ
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class CodeListMixin(models.AbstractModel):
    _name = "code.list.mixin"
    _description = "Code List Mixin"

    code_list_usage_ids = fields.One2many(
        comodel_name="code.list.usage",
        inverse_name="res_id",
        domain=lambda self: [("model", "=", self._name)],
        copy=True,
    )
    code_list_item_ids = fields.Many2many(
        comodel_name="code.list.item",
        compute="_compute_code_list_item_ids",
        string="Code List Items",
        search="_search_code_list_item_ids",
        inverse="_inverse_code_list_item_ids",
    )
    codes_number = fields.Char(
        compute="_compute_codes_number",
        store=True,
        string="Codes No.",
    )

    @api.depends("code_list_usage_ids.code_list_item_id")
    def _compute_code_list_item_ids(self):
        for record in self:
            record.code_list_item_ids = record.code_list_usage_ids.mapped(
                "code_list_item_id"
            )

    @api.model
    def _search_code_list_item_ids(self, operator, value):
        if operator not in ("=", "!=", "ilike", "not ilike", "=ilike", "=like", "like", "not like", "=not like"):
            return []

        # Search for code_list_usage_ids that match the criteria
        usage_ids = self.env["code.list.usage"].search([
            ("code_list_item_id", operator, value),
            ("model", "=", self._name),
        ]).mapped("res_id")

        # Return domain to filter records based on the search
        return [("id", "in", usage_ids)]

    def _inverse_code_list_item_ids(self):
        for record in self:
            # Get the current set of code_list_usage_ids
            existing_usages = self.env['code.list.usage'].search([
                ('model', '=', record._name),
                ('res_id', '=', record.id)
            ])

            # Determine which items to add and which to remove
            current_item_ids = record.code_list_item_ids.ids
            existing_item_ids = existing_usages.mapped('code_list_item_id').ids

            # Add new items
            items_to_add = set(current_item_ids) - set(existing_item_ids)
            for item_id in items_to_add:
                item = self.env['code.list.item'].browse(item_id)
                self.env['code.list.usage'].create({
                    'model': record._name,
                    'res_id': record.id,
                    'code_list_item_id': item.id,
                    'code_list_id': item.list_id.id,
                })

            # Remove items that are no longer in the list
            items_to_remove = set(existing_item_ids) - set(current_item_ids)
            for usage in existing_usages.filtered(lambda u: u.code_list_item_id.id in items_to_remove):
                usage.unlink()

    @api.depends("code_list_item_ids", "code_list_item_ids.code")
    def _compute_codes_number(self):
        for record in self:
            # Get all code list items
            items = record.code_list_item_ids

            # If there are no items, set codes_number to blank
            if not items:
                record.codes_number = ""
                continue

            # Build a set of parent-child relationships
            parent_child_set = set(
                (item.list_id.id, item.child_list_id.id)
                for item in items
                if item.child_list_id
            )

            # Find the root (a list_id that is not a child_list_id)
            all_parents = {parent for parent, _ in parent_child_set}
            all_children = {child for _, child in parent_child_set}
            roots = all_parents - all_children

            # If there is no single root or multiple roots, set codes_number to blank
            if len(roots) != 1:
                record.codes_number = ""
                continue

            # Ensure all items are part of the same hierarchy
            all_related_ids = set()
            visited = set()

            def traverse_hierarchy(node):
                if node in visited:
                    return
                visited.add(node)
                all_related_ids.add(node)
                children = {child for parent, child in parent_child_set if parent == node}
                for child in children:
                    traverse_hierarchy(child)

            root = roots.pop()
            traverse_hierarchy(root)

            # Check if all items are related
            item_list_ids = set(items.mapped("list_id").ids)
            if not item_list_ids.issubset(all_related_ids):
                record.codes_number = ""
                continue

            # Traverse the hierarchy from the root to build the code
            code_sequence = []
            root = root
            visited = set()

            while root:
                if root in visited:
                    # Circular reference detected, set codes_number to blank
                    record.codes_number = ""
                    break

                visited.add(root)
                item = items.filtered(lambda i: i.list_id.id == root)
                if len(item) == 1:
                    code_sequence.append(item.code)

                root = next((child for parent, child in parent_child_set if parent == root), None)

            else:
                # If no circular reference, join the codes in order
                record.codes_number = ".".join(code_sequence)
