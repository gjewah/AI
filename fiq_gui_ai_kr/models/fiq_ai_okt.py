# -*- coding: utf-8 -*-
#
# AI Øktregister (AI KR D5): bakenforliggende tabell som CLAUDE fører selv.
# Gjermund rører den ALDRI — den gir AI KR oversikt over alle økter (Claude Code +
# Cowork) automatisk, i stedet for manuell økt→oppgave-logging. Knytter til
# brain/okt_register.md (git-hjernen), nå som levende Odoo-tabell.

from odoo import api, fields, models


class FiqAiOkt(models.Model):
    _name = "fiq.ai.okt"
    _description = "AI Øktregister (Claude Code + Cowork — Claude fører selv)"
    _order = "sist_aktiv desc, id desc"

    name = fields.Char(string="Økt", required=True, index=True)
    okt_ref = fields.Char(string="Økt-ID / pin", index=True,
                          help="Sesjons-id eller pin-kode Claude bruker for å finne igjen økta.")
    kilde = fields.Selection([
        ("claude_code", "Claude Code"),
        ("cowork", "Cowork"),
        ("annet", "Annet"),
    ], string="Kilde", default="claude_code", index=True)
    company_id = fields.Many2one(
        "res.company", string="Firma", index=True,
        default=lambda self: self.env.company)
    status = fields.Selection([
        ("aktiv", "Aktiv"),
        ("pause", "Pause"),
        ("ferdig", "Ferdig"),
        ("feilet", "Feilet"),
    ], string="Status", default="aktiv", index=True)
    task_id = fields.Many2one(
        "project.task", string="Knyttet oppgave", ondelete="set null",
        help="AI Økter-oppgaven denne økta rapporterer på (valgfri).")
    sammendrag = fields.Text(string="Hva økta gjør")
    start = fields.Datetime(string="Startet", default=fields.Datetime.now)
    sist_aktiv = fields.Datetime(string="Sist aktiv", default=fields.Datetime.now, index=True)

    @api.model
    def registrer_okt(self, name, okt_ref=False, kilde="claude_code",
                      status="aktiv", sammendrag=False, task_id=False, company_id=False):
        """Claude fører øktregisteret selv (get-or-update på okt_ref, ellers navn).
        Ett kall pr. checkpoint → holder AI KR à jour uten menneske-inngripen.
        Returnerer record-id."""
        Okt = self.sudo()
        rec = Okt.browse()
        if okt_ref:
            rec = Okt.search([("okt_ref", "=", okt_ref)], limit=1)
        if not rec and name:
            rec = Okt.search([("name", "=", name)], limit=1)
        vals = {"name": name, "sist_aktiv": fields.Datetime.now()}
        if okt_ref:
            vals["okt_ref"] = okt_ref
        if kilde:
            vals["kilde"] = kilde
        if status:
            vals["status"] = status
        if sammendrag is not False:
            vals["sammendrag"] = sammendrag
        if task_id:
            vals["task_id"] = int(task_id)
        if company_id:
            vals["company_id"] = int(company_id)
        if rec:
            rec.write(vals)
            return rec.id
        return Okt.create(vals).id
