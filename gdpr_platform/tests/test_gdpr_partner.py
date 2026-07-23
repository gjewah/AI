# Copyright 2026 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Tests for GDPR blocking/unblocking on res.partner."""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestGdprPartner(TransactionCase):
    """Test core GDPR block/unblock functionality on res.partner."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Test GDPR Partner",
            "email": "gdpr-test@example.com",
        })

    def test_apply_gdpr_block_sets_fields(self):
        """Blocking a partner sets all GDPR fields correctly."""
        self.partner.apply_gdpr_block(reason="Test block", source="manual")
        self.assertTrue(self.partner.x_gdpr_blocked)
        self.assertEqual(self.partner.x_gdpr_source, "manual")
        self.assertEqual(self.partner.x_gdpr_reason, "Test block")
        self.assertIsNotNone(self.partner.x_gdpr_date)
        self.assertIsNotNone(self.partner.x_gdpr_user_id)

    def test_apply_gdpr_block_adds_to_blacklist(self):
        """Blocking a partner adds email to mail.blacklist."""
        self.partner.apply_gdpr_block(reason="Blacklist test", source="manual")
        blacklisted = self.env["mail.blacklist"].search([
            ("email", "=ilike", self.partner.email)
        ])
        self.assertTrue(blacklisted, "Email should be in mail.blacklist after block")

    def test_apply_gdpr_block_sets_opt_out(self):
        """Blocking a partner sets opt_out = True."""
        self.partner.apply_gdpr_block(reason="Opt-out test", source="manual")
        self.assertTrue(self.partner.opt_out)

    def test_remove_gdpr_block_clears_fields(self):
        """Removing block clears x_gdpr_blocked and related fields."""
        self.partner.apply_gdpr_block(reason="To be removed", source="manual")
        self.partner.remove_gdpr_block()
        self.assertFalse(self.partner.x_gdpr_blocked)
        self.assertFalse(self.partner.x_gdpr_reason)

    def test_remove_gdpr_block_removes_from_blacklist(self):
        """Removing block also removes email from mail.blacklist."""
        self.partner.apply_gdpr_block(reason="BL test", source="manual")
        self.partner.remove_gdpr_block()
        blacklisted = self.env["mail.blacklist"].search([
            ("email", "=ilike", self.partner.email)
        ])
        self.assertFalse(blacklisted, "Email should be removed from blacklist after unblock")

    def test_gdpr_source_values(self):
        """All valid GDPR source values are accepted."""
        for source in ("manual", "unsubscribe", "api", "import"):
            partner = self.env["res.partner"].create({
                "name": f"Partner {source}",
                "email": f"{source}@example.com",
            })
            partner.apply_gdpr_block(reason=f"Test {source}", source=source)
            self.assertEqual(partner.x_gdpr_source, source)

    def test_block_without_email_does_not_crash(self):
        """Blocking a partner with no email should not raise an error."""
        partner = self.env["res.partner"].create({"name": "No Email Partner"})
        try:
            partner.apply_gdpr_block(reason="No email test", source="manual")
        except Exception as e:
            self.fail(f"apply_gdpr_block raised unexpectedly: {e}")
