# Copyright 2026 FIQ
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, exceptions, fields, models


class CodeList(models.Model):
    _name = "code.list"
    _description = "Code List"
    _order = "code, name"

    code = fields.Char(required=False, copy=False)
    name = fields.Char(required=True, copy=False, translate=True)
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    item_ids = fields.One2many(
        comodel_name="code.list.item",
        inverse_name="list_id",
        string="Items",
        domain=[('parent_id', '=', False)], # to reorder only top-level items
    )
    compute_item_codes = fields.Boolean(
        string="Compute Code",
        default=False,
        help="If checked, the code will be computed for items in this list based on their hierarchy and sequence.",
    )
    sequence_separator = fields.Char(
        string="Sequence Separator",
        default=".",
        help="Separator used to build the sequence code for items in this list. For example, '.' or '-' or ''",
    )
    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "A code already exists",
    )

    @api.depends("code", "name")
    def _compute_display_name(self):
        for item in self:
            item.display_name = f"{item.code or ''} {item.name}"

    @api.constrains("compute_item_codes", "sequence_separator")
    def _check_max_9_items_per_level_without_separator(self):
        for record in self:
            if not record.compute_item_codes or record.sequence_separator:
                continue

            levels = self.env["code.list.item"].read_group(
                [("list_id", "=", record.id)],
                ["id:count"],
                ["parent_id"],
            )
            if any(level["id_count"] > 9 for level in levels):
                raise exceptions.ValidationError(
                    "With Compute Code enabled and empty Sequence Separator, each level can contain maximum 9 items."
                )

    # # _rec_names_search = ['name', 'code'] doesn't give the result we want
    # # We want that, when you type an exact code, you get only that code
    # # Exemple : on UNECE Tax category, when you type "S", you should get only
    # # "[S] Standard rate"
    # @api.model
    # def _search_display_name(self, operator, value):
    #     if value and operator == "ilike":
    #         ids = list(self._search([("code", "=", value)]))
    #         if ids:
    #             return [("id", "in", ids)]
    #     return super()._search_display_name(operator, value)

    def action_open_items(self):
        self.ensure_one()
        return {
            "name": f"{self.display_name} Items",
            "type": "ir.actions.act_window",
            "res_model": "code.list.item",
            "view_mode": "list,form",
            "domain": [("list_id", "=", self.id)],
            "context": {
                "default_list_id": self.id,
                "hide_list_id": True,
                # "search_default_my_tags": 1,
                "user_tag_ids": self.env.user.tag_ids.ids,
            },
        }

    child_ids = fields.Many2many(
        comodel_name="code.list",
        relation="code_list_rel",
        column1="parent_id",
        column2="child_id",
        compute="_compute_child_ids",
        store=True,
        string="Child Lists",
    )
    parent_ids = fields.Many2many(
        comodel_name="code.list",
        relation="code_list_rel",
        column1="child_id",
        column2="parent_id",
        readonly=True,
        string="Used by items of",
    )

    @api.depends("item_ids.child_list_id", "child_ids.item_ids.child_list_id")
    def _compute_child_ids(self):
        # Step 1: Build a set of parent-child relations
        parent_child_relations = set(
            (item.list_id.id, item.child_list_id.id)
            for item in self.env["code.list.item"].search([("child_list_id", "!=", False)])
        )

        # Step 2: Compute all descendants recursively
        def get_all_descendants(parent_id, visited):
            if parent_id in visited:
                return set()  # Avoid infinite loops
            visited.add(parent_id)
            children = set(
                child for parent, child in parent_child_relations if parent == parent_id
            )
            for child_id in children.copy():
                children.update(get_all_descendants(child_id, visited))
            return children

        # Step 3: Assign descendants to each record
        for record in self:
            record.child_ids = self.browse(get_all_descendants(record.id, set()))
