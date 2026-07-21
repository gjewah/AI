# -*- coding: utf-8 -*-
"""AI-KONKLUSJONER — det Gjermund skal kunne lese OG STOPPE.

Gjermund 20.07.2026, ordrett:
  «jeg trenger en logg på oppgavene som gjenspeiler AI sine konklusjoner en
   gjenspeiling av md filene som jeg kan lese og spørre om eller be om
   korrigering av når de er feil»

═══ PROBLEMET (målt, ikke antatt) ═══
brain/ 79 filer = 10 244 linjer · docs/ 138 filer = 15 239 linjer
→ 25 483 linjer konklusjoner som øktene skriver TIL HVERANDRE. Gjermund leser ingen.
Er en konklusjon feil, oppdages det først når noe brekker. `spor_kode=False` sto i
to dager — skrevet riktig, feil i praksis — og ble funnet av KR-økta i MIN modul,
ikke av oss som skrev den.

═══ HVA SOM SPEILES (Gjermunds avgrensning) ═══
KANON + alt merket ANTATT eller UVERIFISERT. Verifiserte smådetaljer ingen bygger
på blir i md-filene med lenke. «Alt» ville gitt ~40 poster i dag = støy; «kun kanon»
ville gitt ~5, men da forsvinner de små avgjørelsene som viste seg å være feil —
`spor_kode=False` var ALDRI kanon.

═══ 🛑 «FEIL» ER EN NØDBREMS, IKKE EN KOMMENTAR (Gjermund 21.07) ═══
  «normalt begrunner jeg, men av og til må jeg bruke ordet feil for å få stoppet
   økter som har glemt regelen om kunstpause og starter å bygge på feil konklusjon
   eller ufullstendighet»

DERFOR: `bestrid()` virker UMIDDELBART, uten begrunnelse. Begrunnelsen er valgfri og
kan komme etterpå. Skal Gjermund først formulere seg mens en økt bygger videre på noe
galt, har han tapt tiden han prøver å redde. Stoppen venter ALDRI på forklaringen.

Relatert: `fiq.ai.spor` (sporet eier konklusjonen — økter kommer og går).
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FiqAiKonklusjon(models.Model):
    _name = "fiq.ai.konklusjon"
    _description = "AI-konklusjon (lesbar for mennesket — og mulig å stoppe)"
    _order = "bestridt_forst desc, skrevet desc, id desc"
    _inherit = ["mail.thread"]

    # Sikkerhetsgrader. Rekkefølgen er bevisst: det UTRYGGE står først, fordi det er
    # det Gjermund skal se. En liste som begynner med «verifisert» skjuler risikoen.
    SIKKERHET = [
        ("uverifisert", "Uverifisert — ingen har sjekket"),
        ("antatt", "Antatt — bygger på en antakelse"),
        ("verifisert", "Verifisert — sjekket mot kilden"),
    ]

    name = fields.Char(
        string="Konklusjon", required=True, index=True, tracking=True,
        help="ÉN setning. «Bruk native priority — bygg ikke fiq_prioritet.»")
    grunnlag = fields.Text(
        string="Grunnlag", tracking=True,
        help="Hva konklusjonen bygger på. «Verifisert i project_task.py:154.»")

    sikkerhet = fields.Selection(
        SIKKERHET, string="Sikkerhet", index=True, tracking=True,
        help="Settes av økta som konkluderer — ALDRI i etterkant.")
    er_kanon = fields.Boolean(
        string="Kanon", index=True, tracking=True,
        help="Andre økter skal bygge videre på dette.")

    # 🔴 UTEN GRUNNLAG: umerket konklusjon skal SYNES, ikke gjemme seg.
    # Samme mekanikk som «Uten spor» — og av samme grunn: en VALGFRI mekanisme
    # BRUKES IKKE. `spor_kode` var valgfri i to dager og ble aldri brukt én gang.
    uten_grunnlag = fields.Boolean(
        string="Uten grunnlag", compute="_compute_uten_grunnlag", store=True,
        help="Sikkerhetsgrad mangler. Økta som skrev den har ikke sagt hvor trygg den er.")

    status = fields.Selection([
        ("staar", "Står"),
        ("bestridt", "🛑 Bestridt — arbeid stoppet"),
        ("korrigert", "Korrigert"),
    ], string="Status", default="staar", required=True, index=True, tracking=True)

    bestridt_av = fields.Many2one("res.users", string="Bestridt av", readonly=True)
    bestridt_dato = fields.Datetime(string="Bestridt", readonly=True)
    bestridelse = fields.Text(
        string="Hvorfor feil", tracking=True,
        help="VALGFRI. Stoppen virker uten den — begrunnelsen kan komme etterpå.")

    # Sorteringshjelper: bestridte konklusjoner skal ligge øverst uansett alder.
    bestridt_forst = fields.Boolean(compute="_compute_bestridt_forst", store=True)

    # ── FORANKRING ──────────────────────────────────────────────────────────────
    # Sporet EIER konklusjonen. Økta som skrev den er borte om to dager; konklusjonen
    # skal stå, og ny økt må ARVE at Gjermund har bestridt den.
    spor_id = fields.Many2one(
        "fiq.ai.spor", string="Spor", index=True, ondelete="set null", tracking=True)
    okt_id = fields.Many2one(
        "fiq.ai.okt", string="Skrevet av økt", index=True, ondelete="set null",
        help="Hvem som konkluderte. Historikk — ikke eier.")
    task_id = fields.Many2one(
        "project.task", string="Oppgave", index=True, ondelete="set null", tracking=True,
        help="Ankeret. Uten oppgave får Gjermund verken varsel eller gjenfinning.")

    kilde = fields.Char(
        string="Kilde",
        help="Fil/commit konklusjonen står i, for den som vil grave. "
             "«brain/ai_ktrl_koordinering.md @ bfb604d»")

    skrevet = fields.Datetime(string="Skrevet", default=fields.Datetime.now, index=True)
    company_id = fields.Many2one(
        "res.company", string="Firma", index=True,
        default=lambda self: self.env.company)

    @api.depends("sikkerhet")
    def _compute_uten_grunnlag(self):
        for k in self:
            k.uten_grunnlag = not k.sikkerhet

    @api.depends("status")
    def _compute_bestridt_forst(self):
        for k in self:
            k.bestridt_forst = k.status == "bestridt"

    # ── NØDBREMSEN ──────────────────────────────────────────────────────────────
    def bestrid(self, begrunnelse=False):
        """🛑 STOPP arbeidet på denne konklusjonen. Virker UMIDDELBART.

        Gjermund 21.07: «av og til må jeg bruke ordet feil for å få stoppet økter
        som har glemt regelen om kunstpause og starter å bygge på feil konklusjon».

        Derfor er `begrunnelse` VALGFRI. Krevde vi den, ville nødbremsen vært
        avhengig av at han rekker å formulere seg mens en økt bygger videre — og da
        er tiden han prøver å redde allerede tapt. Begrunnelsen kan komme etterpå.
        """
        for k in self:
            vals = {
                "status": "bestridt",
                "bestridt_av": self.env.user.id,
                "bestridt_dato": fields.Datetime.now(),
            }
            if begrunnelse:
                vals["bestridelse"] = begrunnelse
            k.write(vals)
            # Chatteren BÆRER — registeret peker. Én sannhet, ikke to kopier.
            k._varsle("🛑 <b>BESTRIDT</b> — arbeid på denne konklusjonen skal stoppe.",
                      begrunnelse)
        return True

    def korriger(self, ny_konklusjon, grunnlag=False):
        """Erstatt en bestridt konklusjon med den rettede.

        Den gamle teksten beholdes i chatteren via `tracking=True` — vi overskriver
        aldri historikk. Å skjule hva som VAR konkludert ville gjort loggen verdiløs
        nettopp når den trengs mest.
        """
        self.ensure_one()
        if not ny_konklusjon:
            raise UserError(_("En korreksjon må ha en ny konklusjon."))
        gammel = self.name
        vals = {"name": ny_konklusjon, "status": "korrigert"}
        if grunnlag:
            vals["grunnlag"] = grunnlag
        self.write(vals)
        self._varsle("✅ <b>Korrigert.</b> Var: «%s»" % gammel)
        return True

    def sporsmaal(self, tekst):
        """Gjermund spør om en konklusjon — uten å stoppe arbeidet.

        Mellomtingen mellom «la stå» og nødbremsen: han er usikker, men vil ikke
        stanse noen. Havner i chatteren på oppgaven, der økta ser den.
        """
        self.ensure_one()
        if not tekst:
            raise UserError(_("Skriv hva du lurer på."))
        self._varsle("❓ <b>Spørsmål fra %s:</b>" % self.env.user.name, tekst)
        return True

    def _varsle(self, overskrift, tekst=False):
        """Legg meldingen i chatteren — på oppgaven hvis den finnes, ellers her.

        Oppgaven er å foretrekke: der får Gjermund varsel, historikk og gjenfinning
        gratis fra Odoo. Uten anker havner den på konklusjonen selv — synlig, men
        uten Odoos egne varslingsveier.
        """
        self.ensure_one()
        kropp = "%s<br/>%s" % (overskrift, tekst) if tekst else overskrift
        kropp += "<br/><i>Konklusjon: «%s»</i>" % (self.name or "")
        self.message_post(body=kropp)
        if self.task_id:
            self.task_id.message_post(body=kropp)

    # ── SKRIVING FRA ØKTENE ─────────────────────────────────────────────────────
    @api.model
    def logg(self, konklusjon, sikkerhet=False, er_kanon=False, grunnlag=False,
             spor_kode=False, task_id=False, kilde=False, okt_ref=False):
        """Én økt logger én konklusjon. Kalles av øktene selv.

        AI PK vedtok 21.07 at merking er FELLES REGEL. Men regelen kan ikke hvile på
        at alle husker den: skriver noen uten `sikkerhet`, havner konklusjonen i
        «Uten grunnlag» og SYNES i flaten. Det er hele lærdommen fra spor-saken —
        valgfrie mekanismer brukes ikke, synlige mangler blir rettet.
        """
        vals = {
            "name": konklusjon,
            "grunnlag": grunnlag or False,
            "er_kanon": bool(er_kanon),
            "kilde": kilde or False,
        }
        if sikkerhet in dict(self.SIKKERHET):
            vals["sikkerhet"] = sikkerhet
        if spor_kode:
            vals["spor_id"] = self.env["fiq.ai.spor"]._finn_eller_lag(spor_kode).id
        if task_id:
            vals["task_id"] = int(task_id)
        if okt_ref:
            okt = self.env["fiq.ai.okt"].search([("okt_ref", "=", okt_ref)], limit=1)
            if okt:
                vals["okt_id"] = okt.id
                # Arv sporet fra økta hvis konklusjonen ikke oppga et selv.
                if not vals.get("spor_id") and okt.spor_id:
                    vals["spor_id"] = okt.spor_id.id
        return self.sudo().create(vals).id

    @api.model
    def er_bestridt(self, konklusjon_id):
        """Sjekk FØR du bygger videre: har Gjermund stoppet denne?

        Dette er hele poenget med nødbremsen. En økt som er i ferd med å bygge på en
        konklusjon spør her først — og får «stopp» i stedet for å oppdage det når
        arbeidet er gjort.
        """
        k = self.sudo().browse(int(konklusjon_id)).exists()
        if not k:
            return {"finnes": False}
        return {
            "finnes": True,
            "bestridt": k.status == "bestridt",
            "status": k.status,
            "begrunnelse": k.bestridelse or "",
            "konklusjon": k.name or "",
        }
