# -*- coding: utf-8 -*-
#
# Meldingssenter – per-melding arbeidstilstand + interne notater (V00.05).
# mail.message er delt/flyktig; disse slanke sidecar-modellene lagrer FIQ-arbeidsflyt PÅ en melding:
#   * arbeidsstatus (åpen/pågår/ferdig) – gjør innboksen til en arbeidsflate, ikke bare en liste.
#   * internt notat (team-only) – teamdialog rett på e-posten, USYNLIG for avsender.
# Multicompany: company_id + record rules per firma (se security/fiq_gui_epost_rules.xml).

from odoo import fields, models


class FiqMeldingssenterState(models.Model):
    _name = "fiq.meldingssenter.state"
    _description = "Meldingssenter – arbeidsstatus per melding"

    message_id = fields.Many2one("mail.message", required=True, ondelete="cascade", index=True)
    status = fields.Selection(
        [("apen", "Åpen"), ("pagar", "Pågår"), ("ferdig", "Ferdig")],
        default="apen", required=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True)


class FiqMeldingssenterNote(models.Model):
    _name = "fiq.meldingssenter.note"
    _description = "Meldingssenter – internt notat (team-only) per melding"
    _order = "create_date desc"

    message_id = fields.Many2one("mail.message", required=True, ondelete="cascade", index=True)
    body = fields.Text(required=True)
    user_id = fields.Many2one(
        "res.users", default=lambda self: self.env.user, required=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True)
