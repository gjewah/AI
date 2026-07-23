# -*- coding: utf-8 -*-
import logging

import requests

from odoo import models, api, _

_logger = logging.getLogger(__name__)

# Anthropic Messages API (verified via the claude-api skill):
#  * endpoint  POST https://api.anthropic.com/v1/messages
#  * headers   x-api-key: <key> · anthropic-version: 2023-06-01 · content-type: application/json
#  * body      {model, max_tokens, messages:[{role, content}], system?}
#  * response  {content: [{type: "text", text: "..."}], ...}  → take the text blocks
# The default model id is exactly "claude-opus-4-8" (do NOT append a date suffix).
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 1024
REQUEST_TIMEOUT = 60  # seconds

# ir.config_parameter keys – the human sets these, never the code.
PARAM_KEY = "fiq_gui_ai.anthropic_api_key"
PARAM_MODEL = "fiq_gui_ai.anthropic_model"


def _uten_noekkel(tekst, api_key):
    """Fjern API-nøkkelen fra en tekst før den logges eller vises.

    🔴 SIKKERHET (funnet av enhetstesten 2026-07-23): Anthropics 401-svar og
    `requests`-unntak kan ekko-e forespørselen — inkludert `x-api-key`. Uten
    denne vaskingen havner nøkkelen i klartekst i Odoo.sh-loggen, der den blir
    liggende. Logg og feilmelding skal ALDRI inneholde hemmeligheten.
    """
    tekst = str(tekst)
    if api_key:
        tekst = tekst.replace(api_key, "***")
    return tekst


class FiqGuiAiAssistent(models.AbstractModel):
    """FIQ AI co-worker backend: 'Ask AI for help' (Claude) + presence.

    Stateless helper (AbstractModel) – no records to persist. Runs as
    self.env.user so Odoo record rules govern what data the caller can reach.
    """
    _name = "fiq.gui.ai.assistent"
    _description = "FIQ AI co-worker – assistant"

    # ------------------------------------------------------------------ AI chat
    @api.model
    def spor(self, melding, kontekst=None):
        """Ask the AI (Claude) for help and return the answer as plain text.

        :param melding: the user's question (str).
        :param kontekst: optional extra context prepended as a system note.
        :return: the answer text (str). NEVER raises – on a missing key or any
                 failure it returns a friendly Norwegian message instead.
        """
        melding = (melding or "").strip()
        if not melding:
            return _("Write a question and I'll help you.")

        ICP = self.env["ir.config_parameter"].sudo()
        api_key = (ICP.get_param(PARAM_KEY) or "").strip()
        if not api_key:
            # Key not configured – a human must set it (we never set it here).
            return _(
                "AI is not configured yet. An administrator must add the "
                "Anthropic API key under the 'fiq_gui_ai.anthropic_api_key' "
                "system parameter before the assistant can answer."
            )

        model = (ICP.get_param(PARAM_MODEL) or DEFAULT_MODEL).strip() or DEFAULT_MODEL

        # Build the system note. Runs as the current user – identify them so the
        # answer can be tailored, but never leak data the user can't already see.
        system = _(
            "You are FIQ's helpful AI co-worker inside Odoo. Answer concisely and "
            "in the same language as the user's question. The user is %s."
        ) % (self.env.user.name or _("an Odoo user"))
        if kontekst:
            system = "%s\n\n%s" % (system, str(kontekst))

        payload = {
            "model": model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": melding}],
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        try:
            resp = requests.post(
                ANTHROPIC_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            # Vask bort nøkkelen: 401-svar kan ekko-e headeren tilbake til oss.
            _logger.warning("FIQ AI co-worker: Anthropic request failed: %s",
                            _uten_noekkel(e, api_key))
            return _(
                "AI is unavailable right now – I couldn't reach the assistant. "
                "Please try again in a moment."
            )
        except ValueError as e:  # JSON decode error
            _logger.warning("FIQ AI co-worker: could not parse Anthropic response: %s",
                            _uten_noekkel(e, api_key))
            return _("AI is unavailable right now – I got an unreadable answer.")

        # Response shape: {"content": [{"type": "text", "text": "..."}], ...}
        try:
            blocks = data.get("content") or []
            text = "".join(
                b.get("text", "") for b in blocks if b.get("type") == "text"
            ).strip()
        except (AttributeError, TypeError) as e:
            _logger.warning("FIQ AI co-worker: unexpected Anthropic payload: %s", e)
            text = ""

        if not text:
            return _("AI is unavailable right now – the assistant returned no answer.")
        return text

    # --------------------------------------------------------------- presence
    @api.model
    def get_tilstedevaerelse(self):
        """Return the online status of internal users (Odoo presence).

        ASSUMPTION (noted): Odoo exposes presence via the computed field
        `res.users.im_status` ('online' | 'away' | 'offline'), backed by
        mail.presence / bus. We read it as the current user (record rules apply)
        and keep it minimal and safe: name + status only, no PII beyond the name.
        Share (portal) users are excluded – internal users only.
        """
        Users = self.env["res.users"]
        users = Users.search([("share", "=", False), ("active", "=", True)])
        out = []
        for u in users:
            try:
                status = u.im_status or "offline"
            except Exception:  # field absent in a stripped DB – degrade safely
                status = "offline"
            out.append({
                "id": u.id,
                "name": u.name or "",
                "status": status,
                "online": status in ("online", "away"),
                "is_me": u.id == self.env.uid,
            })
        # Online first, then away, then offline; alphabetical within each group.
        rank = {"online": 0, "away": 1, "offline": 2}
        out.sort(key=lambda r: (rank.get(r["status"], 3), r["name"].lower()))
        return out
