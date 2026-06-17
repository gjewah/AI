# Copyright 2026 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Tests for GDPR SHA256 token generation and URL helpers."""

from odoo.tests.common import TransactionCase


class TestGdprToken(TransactionCase):
    """Test GDPR token generation, consistency and URL helpers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Token Test Partner",
            "email": "tokentest@example.com",
        })
        cls.env["ir.config_parameter"].sudo().set_param(
            "gdpr_platform.token_secret", "test-secret-key"
        )

    def test_token_is_generated(self):
        """Token is generated and stored on partner."""
        token = self.partner._gdpr_compute_token()
        self.assertTrue(token, "Token should be generated")
        self.assertEqual(len(token), 64, "SHA256 hex digest should be 64 chars")

    def test_token_is_deterministic(self):
        """Same partner and secret always produces the same token."""
        token1 = self.partner._gdpr_compute_token()
        token2 = self.partner._gdpr_compute_token()
        self.assertEqual(token1, token2, "Token should be deterministic")

    def test_different_partners_have_different_tokens(self):
        """Different partners produce different tokens."""
        other = self.env["res.partner"].create({
            "name": "Other Partner",
            "email": "other@example.com",
        })
        self.assertNotEqual(
            self.partner._gdpr_compute_token(),
            other._gdpr_compute_token(),
            "Different partners should have different tokens",
        )

    def test_unsubscribe_url_contains_token(self):
        """Unsubscribe URL contains the partner token."""
        url = self.partner._gdpr_unsubscribe_url()
        token = self.partner._gdpr_compute_token()
        self.assertIn(token, url)
        self.assertIn("/gdpr/unsubscribe/", url)

    def test_block_url_contains_token(self):
        """Block URL contains the partner token."""
        url = self.partner._gdpr_block_url()
        token = self.partner._gdpr_compute_token()
        self.assertIn(token, url)
        self.assertIn("/gdpr/block/", url)

    def test_token_changes_if_email_changes(self):
        """Token changes when partner email changes (security)."""
        token_before = self.partner._gdpr_compute_token()
        self.partner.write({"email": "changed@example.com"})
        token_after = self.partner._gdpr_compute_token()
        self.assertNotEqual(
            token_before, token_after,
            "Token should change when email changes",
        )
