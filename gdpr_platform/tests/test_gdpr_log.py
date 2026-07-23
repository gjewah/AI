# Copyright 2026 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Tests for GDPR audit log (gdpr.log)."""

from odoo.tests.common import TransactionCase


class TestGdprLog(TransactionCase):
    """Test that GDPR actions are correctly logged in gdpr.log."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Log Test Partner",
            "email": "logtest@example.com",
        })

    def test_block_creates_log_entry(self):
        """Applying a GDPR block creates a log entry with action=block."""
        before = self.env["gdpr.log"].search_count([("partner_id", "=", self.partner.id)])
        self.partner.apply_gdpr_block(reason="Log test", source="manual")
        after = self.env["gdpr.log"].search_count([("partner_id", "=", self.partner.id)])
        self.assertGreater(after, before, "A log entry should be created on block")

    def test_log_entry_has_correct_action(self):
        """Log entry after block has action='block'."""
        self.partner.apply_gdpr_block(reason="Action test", source="api")
        log = self.env["gdpr.log"].search([
            ("partner_id", "=", self.partner.id),
            ("action", "=", "block"),
        ], limit=1)
        self.assertTrue(log, "Log entry with action=block should exist")
        self.assertEqual(log.source, "api")

    def test_unblock_creates_log_entry(self):
        """Removing a GDPR block creates a log entry with action=unblock."""
        self.partner.apply_gdpr_block(reason="Unblock log test", source="manual")
        self.partner.remove_gdpr_block()
        log = self.env["gdpr.log"].search([
            ("partner_id", "=", self.partner.id),
            ("action", "=", "unblock"),
        ], limit=1)
        self.assertTrue(log, "Log entry with action=unblock should exist")

    def test_log_preserves_partner_name_and_email(self):
        """Log entries preserve partner name and email for deleted partners."""
        self.partner.apply_gdpr_block(reason="Preservation test", source="manual")
        log = self.env["gdpr.log"].search([
            ("partner_id", "=", self.partner.id),
        ], limit=1)
        self.assertEqual(log.partner_name, self.partner.display_name)
        self.assertEqual(log.partner_email, self.partner.email)

    def test_log_records_ip_address(self):
        """Log entry records IP address when provided."""
        self.partner.apply_gdpr_block(
            reason="IP test", source="api", ip_address="192.168.1.1"
        )
        log = self.env["gdpr.log"].search([
            ("partner_id", "=", self.partner.id),
            ("action", "=", "block"),
        ], limit=1)
        self.assertEqual(log.ip_address, "192.168.1.1")
