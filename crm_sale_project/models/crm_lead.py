from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    def _default_sale_order_product_id(self):
        product_id = self.env["ir.config_parameter"].sudo().get_param(
            "crm_sale_project.sale_order_product_id"
        )
        if product_id:
            return int(product_id)
        return False

    @api.depends("order_ids")
    def _compute_sale_order_project_ids(self):
        for r in self:
            r.sale_order_project_ids = r.order_ids.mapped(lambda o: o.project_id).ids

    @api.depends("order_ids")
    def _compute_sale_order_project_count(self):
        for r in self:
            r.sale_order_project_count = len(self.sale_order_project_ids)

    sale_order_product_id = fields.Many2one(
        "product.product",
        string="Sale Order Product",
        help="Product used when creating a sale order from the opportunity.",
        default=lambda self: self._default_sale_order_product_id(),
    )
    sale_order_project_ids = fields.Many2many(
        "project.project",
        compute="_compute_sale_order_project_ids",
        string="Sale Order Projects",
    )
    sale_order_project_count = fields.Integer(
        compute="_compute_sale_order_project_count",
        string="Sale Order Project Count",
    )
    project_address = fields.Char("Project Address")

    @api.depends("project_address")
    def _compute_name(self):
        return super()._compute_name()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "name" in vals and not vals.get("project_address"):
                vals["project_address"] = vals["name"]
            if "partner_name" in vals and not vals.get("contact_name"):
                vals["contact_name"] = vals["partner_name"]
        return super().create(vals_list)

    def get_partner_name_and_project_address(self, delimiter):
        self.ensure_one()
        result = []
        partner = self.partner_id
        if partner and partner.short_name:
            result.append(partner.short_name)
        elif partner and partner.name:
            result.append(partner.name)
        elif self.partner_name:
            result.append(self.partner_name)
        if self.project_address:
            result.append(self.project_address)
        if result:
            return delimiter.join(result)
        else:
            return self.id

    def action_create_sale_order_and_project(self):
        self.ensure_one()
        self.create_sale_order_and_project()
        self.move_attachments_to_task_or_project()

    def create_sale_order_and_project(self):
        # Get sale order PRODUCT >> project TEMPLATE
        product = self.sale_order_product_id
        if not product:
            raise UserError("Missing a sale order product (set on the lead or in Settings).")

        # Check other values
        # if product.project_template_id and getattr(product.project_template_id, "is_fsm", False):
        #     raise UserError("The product's project template is for field service management. Please select another product.")
        if not self.partner_id: raise UserError("Missing a contact.")
        # TODO: Ask the user if the contact should really not be a company.
        # if not self.partner_id.is_company: raise UserError("Contact should be a company.")

        # Create
        if not self.sale_order_project_ids:
            if not self.company_id:
                raise UserError("Missing a salesperson.")
            order = self.env["sale.order"].create(
                {
                    "partner_id": self.partner_id.id, # Customer from the opportunity
                    "opportunity_id": self.id,        # Link to the opportunity
                    "company_id": self.company_id.id, # Company of the opportunity
                    "user_id": self.user_id.id,       # Salesman
                    "campaign_id": self.campaign_id.id,
                    "medium_id": self.medium_id.id,
                    "source_id": self.source_id.id,
                    "project_id": self.project_id.id, # if empty, Odoo will fill it based on the product service_tracking
                }
            )
            order_line = self.env["sale.order.line"].create(
                {
                    "order_id": order.id,
                    "name": order.partner_id.display_name,
                    "product_id": product.id,
                }
            )
            order.action_confirm() # will create project and/or task
            return order

    def move_attachments_to_task_or_project(self):
        """Associate existing CRM lead attachments with project/task depending on service_tracking"""
        self.ensure_one()

        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'crm.lead'),
            ('res_id', '=', self.id)
        ])
        if not attachments:
            return

        product = self.sale_order_product_id
        if not product:
            raise UserError(_("No product is selected for the CRM lead name %s.") % (self.name))

        service_tracking = product.service_tracking
        if not service_tracking:
            raise UserError(_("Product '%s' has no service_tracking.") % (product.name))

        Project = self.env['project.project']
        Task = self.env['project.task']

        if service_tracking == "project_only":
            projects = self.sale_order_project_ids
            if len(projects) != 1:
                raise UserError(_("There must be exactly one project related to CRM lead '%s'. Found: %d") % (self.name, len(projects)))
            project = projects[0]

            attachments.write({
                'res_model': 'project.project',
                'res_id': project.id,
            })

        elif service_tracking == "task_global_project":
            tasks = self.env['project.task'].search([('sale_line_id.order_id.opportunity_id', '=', self.id)])
            if len(tasks) != 1:
                raise UserError(_("There must be exactly one task related to CRM lead '%s'. Found: %d") % (self.name, len(tasks)))
            task = tasks[0]

            attachments.write({
                'res_model': 'project.task',
                'res_id': task.id,
            })

        elif service_tracking == "task_in_project":
            projects = self.sale_order_project_ids #.filtered(lambda p: p.name == order_line._timesheet_get_project_name())
            if len(projects) != 1:
                raise UserError(_("There must be exactly one project related to CRM lead '%s'. Found: %d") % (self.name, len(projects)))
            project = projects[0]

            order_lines = self.sale_order_project_ids.mapped("sale_line_id")
            if len(order_lines) != 1:
                raise ValidationError(f"{len(order_lines)} project order lines found. To move attachments, there should be exactly 1.")
            order_line = order_lines[0]
            tasks = project.task_ids.filtered(lambda t: t.name == order_line._timesheet_get_task_name())
            if len(tasks) != 1:
                raise UserError(_("There must be exactly one task related to CRM lead '%s'. Found: %d") % (self.name, len(tasks)))
            task = tasks[0]

            attachments.write({
                'res_model': 'project.task',
                'res_id': task.id,
            })
        else:
            raise UserError(_("Unknown service tracking type: %s") % service_tracking)
