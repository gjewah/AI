from odoo.tests.common import TransactionCase


class TestCrmLead(TransactionCase):

    def test_name(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "crm_name.crm_lead_name_expression",
            "{r.partner_id.short_name if r.partner_id.short_name else r.partner_id.name}",
        )
        contact = self.env["res.partner"].create({"name": "Test Contact"})
        # Contact name
        lead = self.env["crm.lead"].create({"partner_id": contact.id, "name": "/"})
        self.assertEqual(lead.name, "Test Contact")
        # Contact short name
        contact.short_name = "TC"
        self.assertEqual(lead.name, "TC")
