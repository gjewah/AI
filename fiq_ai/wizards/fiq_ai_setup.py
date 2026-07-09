# -*- coding: utf-8 -*-
"""FIQ AI — 2-stegs oppsett-wizard for Claude-nøkkelen.

Steg 1: lenke til Anthropic Console for å hente en API-nøkkel.
Steg 2: lim inn nøkkelen → lagres i systemparameteren ``ai.anthropic_key`` +
        valgfri live-test mot Claude.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

KEY_PARAM = "ai.anthropic_key"
CONSOLE_URL = "https://console.anthropic.com/settings/keys"


class FiqAiSetupWizard(models.TransientModel):
    _name = "fiq.ai.setup.wizard"
    _description = "FIQ AI — oppsett av Claude-nøkkel (2 steg)"

    state = fields.Selection(
        [("step1", "Steg 1 — hent nøkkel"), ("step2", "Steg 2 — lim inn nøkkel")],
        default="step1", string="Steg")
    anthropic_key = fields.Char(string="Claude API-nøkkel")
    key_is_set = fields.Boolean(string="Nøkkel alt satt", compute="_compute_key_is_set")
    test_result = fields.Text(string="Resultat", readonly=True)

    def _compute_key_is_set(self):
        cur = self.env["ir.config_parameter"].sudo().get_param(KEY_PARAM)
        for wiz in self:
            wiz.key_is_set = bool(cur)

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_console(self):
        """Steg 1: åpne Anthropic Console i ny fane for å lage/kopiere en nøkkel."""
        return {"type": "ir.actions.act_url", "url": CONSOLE_URL, "target": "new"}

    def action_next(self):
        self.state = "step2"
        return self._reopen()

    def action_back(self):
        self.state = "step1"
        return self._reopen()

    def action_save_and_test(self):
        """Steg 2: lagre nøkkelen og test mot Claude."""
        key = (self.anthropic_key or "").strip()
        if not key:
            raise UserError(_("Lim inn Claude-nøkkelen (starter med «sk-ant-») først."))
        self.env["ir.config_parameter"].sudo().set_param(KEY_PARAM, key)
        try:
            ans = self.env["fiq.ai"].chat(_("Svar med nøyaktig denne teksten: OK"))
            self.test_result = _("✅ Nøkkel lagret. Claude svarte: «%s». «Spør AI» er nå aktiv.") % ans
        except Exception as exc:  # noqa: BLE001 — vis feilen til brukeren
            self.test_result = _(
                "⚠ Nøkkelen er lagret, men testen mot Claude feilet:\n%s\n"
                "Sjekk at nøkkelen er riktig og aktiv i Anthropic Console."
            ) % str(exc)
        # tøm feltet fra minnet så nøkkelen ikke blir liggende i wizard-recorden
        self.anthropic_key = False
        return self._reopen()
