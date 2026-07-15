import base64

from odoo.exceptions import ValidationError, UserError
from odoo.tests.common import TransactionCase


class TestCrmLead(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Helper: Make expression handling valid
        cls.env["ir.config_parameter"].sudo().set_param(
            "crm_name.crm_lead_name_expression",
            "{r.get_partner_name_and_project_address(' - ')}",
        )

        # Partner
        cls.partner = cls.env["res.partner"].create(
            {"name": "Contact", "is_company": True}
        )

        # CRM Lead
        cls.lead = cls.env["crm.lead"].create(
            {
                "name": "/",
                "partner_name": "Contact Name",
                "project_address": "Project Address",
                "partner_id": cls.partner.id,
            }
        )

        # === Create 3 product variants for testing ===

        # Project Only
        cls.product_project_only = cls.env["product.product"].create({
            "name": "Product Project Only",
            "type": "service",
            "service_tracking": "project_only",
        })

        # Task Global Project
        cls.original_global_project = cls.env["project.project"].create({
            "name": "Original Global Project"
        })

        cls.product_task_global = cls.env["product.product"].create({
            "name": "Product Task Global",
            "type": "service",
            "service_tracking": "task_global_project",
            "project_id": cls.original_global_project.id,
        })

        # Task In Project
        cls.product_task_in_project = cls.env["product.product"].create({
            "name": "Product Task In Project",
            "type": "service",
            "service_tracking": "task_in_project",
        })

        # An attachment that must be moved
        cls.attachment = cls.env["ir.attachment"].create({
            "name": "Test Attachment",
            "type": "binary",
            "datas": base64.b64encode(b"ABC"),
            "res_model": "crm.lead",
            "res_id": cls.lead.id,
        })

    # ----------------------------------------------------------------------
    # task_in_project
    # ----------------------------------------------------------------------
    def test_action_create_sale_order_and_project__task_in_project(self):
        lead = self.lead
        lead.sale_order_product_id = self.product_task_in_project.id

        lead.action_create_sale_order_and_project()

        # Validate project creation
        self.assertEqual(len(lead.sale_order_project_ids), 1)
        project = lead.sale_order_project_ids

        # Validate task creation
        self.assertEqual(len(project.task_ids), 1)
        task = project.task_ids

        correct_name = f"{lead.order_ids.name} {lead.name}"

        self.assertEqual(project.name, correct_name)
        self.assertEqual(task.name, correct_name)

        # Attachment moved to task
        self.assertEqual(self.attachment.res_model, "project.task")
        self.assertEqual(self.attachment.res_id, task.id)

    # ----------------------------------------------------------------------
    # task_global_project
    # ----------------------------------------------------------------------
    def test_action_create_sale_order_and_project__task_global_project(self):
        lead = self.lead
        lead.sale_order_product_id = self.product_task_global.id

        # crm_timesheet compatibility: lead.project_id must point to the global project
        lead.project_id = self.original_global_project.id

        lead.action_create_sale_order_and_project()

        # For task_global_project, the project must remain the original
        self.assertEqual(lead.sale_order_project_ids, lead.project_id)

        # Validate task creation
        project = lead.sale_order_project_ids
        self.assertEqual(len(project.task_ids), 1)
        task = project.task_ids

        expected_name = f"{lead.order_ids.name} {lead.name}"
        self.assertEqual(task.name, expected_name)

        # Attachment moved to task
        self.assertEqual(self.attachment.res_model, "project.task")
        self.assertEqual(self.attachment.res_id, task.id)

    # ----------------------------------------------------------------------
    # project_only
    # ----------------------------------------------------------------------
    def test_action_create_sale_order_and_project__project_only(self):
        lead = self.lead
        lead.sale_order_product_id = self.product_project_only.id

        lead.action_create_sale_order_and_project()

        # Must have exactly one project created
        self.assertEqual(len(lead.sale_order_project_ids), 1)
        project = lead.sale_order_project_ids

        expected_name = f"{lead.order_ids.name} {lead.name}"
        self.assertEqual(project.name, expected_name)

        # Attachment moved to project
        self.assertEqual(self.attachment.res_model, "project.project")
        self.assertEqual(self.attachment.res_id, project.id)

    # ----------------------------------------------------------------------
    # Expression validation
    # ----------------------------------------------------------------------
    def test_crm_lead_valid_field_and_method(self):
        self.env["crm.lead"].raise_error_if_invalid_expression(
            "{r.id} {r.get_partner_name_and_project_address(' - ')}"
        )

    def test_crm_lead_invalid_field(self):
        with self.assertRaises(ValidationError):
            self.env["crm.lead"].raise_error_if_invalid_expression(
                "{r.non_existing_field}"
            )

    def test_crm_lead_invalid_method(self):
        with self.assertRaises(ValidationError):
            self.env["crm.lead"].raise_error_if_invalid_expression(
                "{r.non_existing_method()}"
            )
