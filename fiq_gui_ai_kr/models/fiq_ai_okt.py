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

    # ── SPOR-TILHØRIGHET (Gjermund 19.07) ───────────────────────────────────────
    # «Alle økter bør klassifiseres og samles inn under respektive prosjektspor.
    #  De øktene som flyter over flere spor må vise dette.»
    # Valgt modell: ETT hovedspor + gjestespor. Entydig eierskap, synlig overlapp —
    # så ingen tror to spor eier det samme. Vises som «AI KR (+ Prosjekt)».
    spor_id = fields.Many2one(
        "fiq.ai.spor", string="Hovedspor", index=True, ondelete="set null",
        help="Sporet økta hører hjemme i. Den varige enheten — økter kommer og går.")
    gjestespor_ids = fields.Many2many(
        "fiq.ai.spor", "fiq_ai_okt_gjestespor_rel", "okt_id", "spor_id",
        string="Jobber også i",
        help="Andre spor økta skriver i. Eksempel: AI KR eier sjekkliste-motoren "
             "som ligger i Prosjekt-modulen.")
    spor_visning = fields.Char(string="Spor", compute="_compute_spor_visning",
                               help="«AI KR (+ Prosjekt)» — hovedspor med gjestespor bak.")

    @api.depends("spor_id", "spor_id.name", "gjestespor_ids", "gjestespor_ids.name")
    def _compute_spor_visning(self):
        for o in self:
            if not o.spor_id:
                o.spor_visning = ""
                continue
            navn = o.spor_id.kode or o.spor_id.name
            gjester = [g.kode or g.name for g in o.gjestespor_ids if g != o.spor_id]
            o.spor_visning = "%s (+ %s)" % (navn, ", ".join(gjester)) if gjester else navn

    @api.model
    def registrer_okt(self, name, okt_ref=False, kilde="claude_code",
                      status="aktiv", sammendrag=False, task_id=False, company_id=False,
                      spor_kode=False, gjestespor_koder=False):
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
        # Spor-tilhørighet: økta melder hvilket spor den hører til, og hvilke andre
        # den skriver i. Sporet opprettes hvis det ikke finnes — da slipper vi at en
        # økt faller utenfor bare fordi ingen har opprettet sporet på forhånd.
        if spor_kode:
            vals["spor_id"] = self.env["fiq.ai.spor"]._finn_eller_lag(spor_kode).id
        if gjestespor_koder:
            Spor = self.env["fiq.ai.spor"]
            ids = [Spor._finn_eller_lag(k).id for k in gjestespor_koder if k]
            vals["gjestespor_ids"] = [(6, 0, ids)]
        if rec:
            rec.write(vals)
            return rec.id
        return Okt.create(vals).id
