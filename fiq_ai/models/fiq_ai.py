# -*- coding: utf-8 -*-
import json
import logging
import os

from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
# Cost-effective default for summaries/search; callers may pass a stronger model.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class FiqAi(models.TransientModel):
    _name = "fiq.ai"
    _description = "FIQ AI connector (Claude via Anthropic API)"

    @api.model
    def _api_key(self):
        """API key: env var first (most secure, e.g. Odoo.sh), then system parameter."""
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            key = self.env["ir.config_parameter"].sudo().get_param("fiq_ai.anthropic_api_key")
        return (key or "").strip()

    @api.model
    def chat(self, prompt, system=None, model=None, max_tokens=1024):
        """Call Claude (Anthropic Messages API) and return plain text.

        Runs on behalf of the current user. The prompt content is sent to the
        Anthropic API for processing (external service) — callers are responsible
        for not passing data that must not leave the tenant.
        """
        if requests is None:
            raise UserError(_("Python-pakken 'requests' mangler på serveren."))
        if not prompt:
            return ""
        key = self._api_key()
        if not key:
            raise UserError(_(
                "Anthropic API-nøkkel er ikke satt. Sett miljøvariabelen ANTHROPIC_API_KEY "
                "eller system-parameteren 'fiq_ai.anthropic_api_key'."))
        payload = {
            "model": model or DEFAULT_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        try:
            resp = requests.post(ANTHROPIC_URL, headers=headers,
                                 data=json.dumps(payload), timeout=60)
        except Exception as e:  # network / timeout
            _logger.warning("FIQ AI: kunne ikke nå Anthropic-API: %s", e)
            raise UserError(_("Klarte ikke å nå Anthropic-API-et: %s") % e)
        if resp.status_code != 200:
            _logger.warning("FIQ AI: Anthropic svarte %s: %s", resp.status_code, resp.text[:500])
            raise UserError(_("Anthropic-API svarte %s. Sjekk nøkkel/kvote.") % resp.status_code)
        data = resp.json()
        parts = data.get("content") or []
        text = "".join(b.get("text", "") for b in parts if isinstance(b, dict) and b.get("type") == "text")
        return text.strip()

    @api.model
    def ping(self):
        """Self-test: verifies key + connectivity. Returns the model's reply."""
        return self.chat("Svar med nøyaktig ordet: OK", max_tokens=10)
