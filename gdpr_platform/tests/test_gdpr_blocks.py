# Copyright 2026 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Tests for GDPR ORM guards across all models."""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestGdprBlocks(TransactionCase):
    """Test that blocked partners are prevented from communication across all models."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Blocked Partner",
            "email": "blocked@example.com",
        })
        cls.partner.apply_gdpr_block(reason="ORM guard tests", source="manual")

    def test_crm_lead_blocked_on_create(self):
        """Creating a CRM lead for a blocked partner raises UserError."""
        with self.assertRaises(UserError):
            self.env["crm.lead"].create({
                "name": "Test Lead",
                "partner_id": self.partner.id,
            })

    def test_sale_order_blocked_on_create(self):
        """Creating a sale order for a blocked partner raises UserError."""
        with self.assertRaises(UserError):
            self.env["sale.order"].create({
                "partner_id": self.partner.id,
            })

    def test_helpdesk_ticket_blocked_on_create(self):
        """Creating a helpdesk ticket for a blocked partner raises UserError."""
        with self.assertRaises(UserError):
            self.env["helpdesk.ticket"].create({
                "name": "Test Ticket",
                "partner_id": self.partner.id,
            })

    def test_mail_activity_blocked_on_create(self):
        """Creating a mail activity for a blocked partner raises UserError."""
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        with self.assertRaises(UserError):
            self.env["mail.activity"].create({
                "res_model": "res.partner",
                "res_id": self.partner.id,
                "activity_type_id": activity_type.id,
                "summary": "Test Activity",
            })

    def test_mailing_contact_blocked_on_create(self):
        """Adding a blocked email to a mailing list raises UserError."""
        mailing_list = self.env["mailing.list"].create({"name": "Test List"})
        with self.assertRaises(UserError):
            self.env["mailing.contact"].create({
                "name": "Blocked",
                "email": self.partner.email,
                "list_ids": [(4, mailing_list.id)],
            })

    def test_marketing_participant_blocked_on_create(self):
        """Creating a marketing participant for blocked partner raises UserError."""
        activity = self.env["marketing.activity"].create({
            "name": "Test Activity",
            "activity_type": "email",
        })
        campaign = self.env["marketing.campaign"].create({
            "name": "Test Campaign",
            "marketing_activity_ids": [(4, activity.id)],
        })
        with self.assertRaises(UserError):
            self.env["marketing.participant"].create({
                "campaign_id": campaign.id,
                "partner_id": self.partner.id,
            })

    def test_unblocked_partner_can_create_lead(self):
        """After unblocking, creating a CRM lead succeeds."""
        self.partner.remove_gdpr_block()
        lead = self.env["crm.lead"].create({
            "name": "Lead after unblock",
            "partner_id": self.partner.id,
        })
        self.assertTrue(lead.exists())
        # Re-block for other tests
        self.partner.apply_gdpr_block(reason="Re-block", source="manual")
