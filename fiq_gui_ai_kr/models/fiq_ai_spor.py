# -*- coding: utf-8 -*-
"""AI PROSJEKTSPOR — økter samles under spor, ikke omvendt.

Gjermund 19.07.2026, ordrett:
  «Jeg ser ikke på dette som økter men som prosjekter og det er den tullete
   økt-opplegget til Claude som skaper kaoset.»
  «Alle økter bør klassifiseres og samles inn under respektive prosjektspor.
   De øktene som flyter over flere spor må vise dette.»

DERFOR: sporet er den varige enheten. Økter er bare arbeidsperioder inne i et spor —
de kommer og går når Claude går tom for kontekst, og det skal ikke være Gjermunds problem.

═══ VERSJONSNUMMERERING (Gjermunds modell, 19.07) ═══
  00.xx  = bygges, står IKKE i Odoo ennå
  01.00  = første gang modulen faktisk STÅR og virker i Odoo   ← automatisk detektert
  01.xx  = videre arbeid på den milepælen
  → mot godkjent ferdig prosjekt

Hovedtallet bumpes AUTOMATISK når modulen er `installed` i basen (Gjermunds valg:
«Når modulen står i Odoo»). Ingen manuell bokføring — systemet ser det selv.

═══ KRYSS-SPOR (Gjermunds valg: hovedspor + gjestespor) ═══
Hver økt har ETT hovedspor (der den hører hjemme) + gjestespor den også jobber i.
Vises som «AI KR (+ Prosjekt)». Entydig eierskap, synlig overlapp — så ingen tror
to spor eier det samme.
"""

from odoo import api, fields, models


class FiqAiSpor(models.Model):
    _name = "fiq.ai.spor"
    _description = "AI Prosjektspor (den varige enheten — økter er arbeidsperioder i den)"
    _order = "kode, id"

    name = fields.Char(string="Spor", required=True, index=True,
                       help="F.eks. «AI Kontrollrom», «Prosjekt», «Kommunikasjon».")
    kode = fields.Char(string="Kode", index=True,
                       help="Kort kode brukt i øktnavn, f.eks. «AI KR», «PRJ», «KOMM».")
    modul = fields.Char(string="Odoo-modul", index=True,
                        help="Teknisk modulnavn sporet bygger, f.eks. fiq_gui_ai_kr. "
                             "Brukes til å detektere milepælen automatisk.")
    beskrivelse = fields.Text(string="Hva sporet leverer")

    # ── VERSJON ─────────────────────────────────────────────────────────────────
    versjon_hoved = fields.Integer(
        string="Milepæl", default=0,
        help="00 = ikke i Odoo ennå · 01 = står og virker i Odoo · videre mot ferdig.")
    versjon_lop = fields.Integer(
        string="Løpenr", default=0,
        help="Teller opp for hver ny økt innenfor samme milepæl.")
    versjon = fields.Char(string="Versjon", compute="_compute_versjon", store=True,
                          help="«00.03» — vises i øktnavnet.")

    modul_installert = fields.Boolean(
        string="Står i Odoo", compute="_compute_modul_status",
        help="Leses fra ir.module.module. Utløser milepæl 01 første gang den er sann.")
    modul_versjon = fields.Char(string="Modulversjon", compute="_compute_modul_status")

    status = fields.Selection([
        ("planlagt", "Planlagt"),
        ("bygges", "Bygges"),
        ("i_odoo", "Står i Odoo"),
        ("testet", "Testet"),
        ("produksjon", "I Production"),
        ("godkjent", "Godkjent ferdig"),
    ], string="Status", default="bygges", index=True)

    okt_ids = fields.One2many("fiq.ai.okt", "spor_id", string="Økter i sporet")
    antall_okter = fields.Integer(compute="_compute_okter", store=True)
    aktive_okter = fields.Integer(compute="_compute_okter", store=True)
    company_id = fields.Many2one("res.company", string="Firma", index=True,
                                 default=lambda self: self.env.company)

    _sql_constraints = [
        ("kode_unik", "unique(kode, company_id)", "Sporkoden må være unik per firma."),
    ]

    @api.depends("versjon_hoved", "versjon_lop")
    def _compute_versjon(self):
        for s in self:
            s.versjon = "%02d.%02d" % (s.versjon_hoved or 0, s.versjon_lop or 0)

    @api.depends("okt_ids", "okt_ids.status")
    def _compute_okter(self):
        for s in self:
            s.antall_okter = len(s.okt_ids)
            s.aktive_okter = len(s.okt_ids.filtered(lambda o: o.status == "aktiv"))

    def _compute_modul_status(self):
        """Les faktisk tilstand fra Odoo — ikke fra en påstand i et dokument."""
        Mod = self.env["ir.module.module"].sudo()
        for s in self:
            s.modul_installert = False
            s.modul_versjon = ""
            if not s.modul:
                continue
            m = Mod.search([("name", "=", s.modul)], limit=1)
            if m:
                s.modul_installert = m.state == "installed"
                s.modul_versjon = m.latest_version or ""

    @api.model
    def sjekk_milepaeler(self):
        """Bump 00 → 01 for spor der modulen nå faktisk STÅR i Odoo.

        Gjermunds valg 19.07: hovedtallet bumpes «når modulen står i Odoo» — automatisk
        detekterbart, ingen manuell bokføring. Kjøres av cron og ved hver visning.

        Bumper KUN 00 → 01. Videre milepæler (testet/production/godkjent) er
        Gjermunds beslutning, ikke noe systemet skal gjette seg til.
        """
        bumpet = []
        for s in self.search([("versjon_hoved", "=", 0), ("modul", "!=", False)]):
            s._compute_modul_status()
            if s.modul_installert:
                s.write({"versjon_hoved": 1, "versjon_lop": 0, "status": "i_odoo"})
                bumpet.append(s.name)
        return bumpet

    @api.model
    def _finn_eller_lag(self, kode):
        """Slå opp et spor på kode — opprett det hvis det ikke finnes.

        Uten dette faller en økt utenfor bare fordi ingen har opprettet sporet på
        forhånd. Da mister vi nettopp den oversikten sporene finnes for å gi.
        """
        kode = (kode or "").strip()
        if not kode:
            return self.browse()
        spor = self.search([("kode", "=ilike", kode)], limit=1)
        if spor:
            return spor
        return self.create({"name": kode, "kode": kode, "status": "bygges"})

    def neste_okt_navn(self):
        """Navnet neste økt i sporet skal ha — «0.00 8.50 AI KR (01.02)».

        Systemet kan forberede alt, men KAN IKKE starte økta selv: en økt som går tom
        for kontekst kan ikke opprette en ny. Det klikket er Gjermunds. Vi gjør det
        derfor så billig som mulig — navnet er klart, nummeret er tildelt.
        """
        self.ensure_one()
        neste = (self.versjon_lop or 0) + 1
        return "0.00 8.50 %s (%02d.%02d)" % (self.kode or self.name,
                                             self.versjon_hoved or 0, neste)
