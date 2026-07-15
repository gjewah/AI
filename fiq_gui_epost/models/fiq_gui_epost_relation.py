# -*- coding: utf-8 -*-
#
# Meldingssenter – relasjonsmodell «én kontakt, mange relasjoner» (§C.2, V00.05).
# Løser Odoos dublett-problem: samme person kan være tilknyttet flere entiteter samtidig
# (eier · leverandør · prosjektleder · forvalter …). Slank FIQ-egen modell (ikke OCA-tung),
# i tråd med [[minimize_oca]]. Relasjonstypene er generiske (v1, Selection) — kan bli en egen
# config-drevet type-modell senere («vi kan alltids utvikle videre», Gjermund 2026-07-15).
# Multicompany: company_id + record rule.

from odoo import fields, models


class FiqPartnerRelation(models.Model):
    _name = "fiq.partner.relation"
    _description = "FIQ – relasjon mellom to kontakter (én kontakt, mange relasjoner)"
    _order = "date_start desc, id desc"

    partner_id = fields.Many2one(
        "res.partner", string="Kontakt", required=True, ondelete="cascade", index=True)
    related_partner_id = fields.Many2one(
        "res.partner", string="Relatert kontakt", required=True, ondelete="cascade", index=True)
    relation_type = fields.Selection([
        ("prosjektleder", "Prosjektleder"),
        ("eier", "Eier"),
        ("eiendomsbesitter", "Eiendomsbesitter"),
        ("leverandor", "Leverandør"),
        ("kunde", "Kunde"),
        ("underentreprenor", "Underentreprenør"),
        ("ansatt", "Ansatt"),
        ("forvalter", "Forvalter"),
        ("vaktmester", "Vaktmester"),
        ("ekstern_pl", "Ekstern PL"),
        ("oppdragsgiver", "Oppdragsgiver"),
        ("annet", "Annet"),
    ], string="Relasjonstype", required=True, default="annet")
    date_start = fields.Date(string="Gyldig fra")
    date_end = fields.Date(string="Gyldig til")
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True)
