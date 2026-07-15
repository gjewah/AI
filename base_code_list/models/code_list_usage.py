from odoo import api, fields, models

class CodeListUsage(models.Model):
    _name = "code.list.usage"
    _description = "code.list.usage"
    _unique_code_list_item = models.Constraint(
        "UNIQUE(model, res_id, code_list_id)",
        "The code list can be linked only once to the same resource!",
    )

    model = fields.Char()
    res_id = fields.Many2oneReference(
        model_field="model",
        string="Resource ID",
    )
    code_list_id = fields.Many2one(
        comodel_name="code.list",
    )
    code_list_item_id = fields.Many2one(
        comodel_name="code.list.item",
    )
    resource_id = fields.Reference(
        selection=[('res.partner', 'Contacts')],
        string="Resource",
        compute="_compute_resource_id",
        inverse="_inverse_resource_id",
        store=True,
    )

    @api.depends("model", "res_id")
    def _compute_resource_id(self):
        for record in self:
            if record.model and record.res_id:
                record.resource_id = f"{record.model},{record.res_id}"
            else:
                record.resource_id = False

    def _inverse_resource_id(self):
        for record in self:
            if record.resource_id:
                record.model = record.resource_id._name
                record.res_id = record.resource_id.id
            else:
                record.model = False
                record.res_id = False

    def action_select_item(self):
        """
        Opens a popup window to select a code.list.item.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Code List Item',
            'res_model': 'code.list.item',
            'view_mode': 'list,form',
            'target': 'new',
            'domain': [('list_id', '=', self.code_list_id.id)],
            'context': {
                "search_default_my_tags": 1,
                "user_tag_ids": self.env.user.tag_ids.ids,
            },
        }
