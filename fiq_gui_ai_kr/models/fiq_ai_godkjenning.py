"""GODKJENNINGSKØEN — det som fjerner klikkingen fra Gjermunds hverdag.

Gjermund 22.07.2026, ordrett:
  «Jeg rekker knapt gjøre annet enn å prøve å holde progresjon ved å trykke ALLOW
   hvert tredje til hvert femte sekund. Det er umulig å få progresjon i dette miljøet.»

Fasit: artifact 13184ec2 «ai_kr_utkast_01», seksjonen «Godkjenningskø» —
klikket kontroll for kontroll 22.07 før modellen ble skrevet.

═══ FIRE SVAR, IKKE TO ═══
Fasiten har fire knapper, og den fjerde er hele poenget:
  🟢  Godkjent      — ja, denne gangen
  🟠  Ja, men…      — ja, med et forbehold økta MÅ lese før den fortsetter
  🔴  Nei           — stopp
  🟢⭐ Alltid        — ja, og SLUTT Å SPØRRE om dette

`alltid` er svaret på sitatet over. Uten den fortsetter samme spørsmål å komme
tilbake i det uendelige. Med den svarer Gjermund ÉN gang, og systemet husker.

═══ ROLLE-VARIANTEN ═══
Rad tre i fasiten har andre knapper: «🟢 Jeg gjør det · 🟠 Senere · 🔴 Dropp».
Det er ikke en godkjenning — det er en OPPGAVE til Gjermund («skaff Admin-nøkkel»).
Samme kø, ulik knapperad, styrt av `art`.

═══ HVORFOR DETTE HØRER HJEMME I AI KR ═══
Køen er tverrgående: alle økter melder hit, ett sted å svare. Ligger den i hver
flate, er vi tilbake til å hoppe mellom rom — nøyaktig det Gjermund ba oss fjerne.

Relatert: [[fiq.ai.konklusjon]] (nødbremsen — stopp noe som ALT er konkludert),
denne modellen (svar FØR noe skjer).
"""

from typing import ClassVar

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FiqAiGodkjenning(models.Model):
    _name = "fiq.ai.godkjenning"
    _description = (
        "Godkjenningskø (Gjermund svarer ÉN gang — «Alltid» stopper gjentakelsen)"
    )
    _order = "ubesvart desc, haster desc, opprettet desc, id desc"
    _inherit = ["mail.thread"]  # noqa: RUF012

    name = fields.Char(
        string="Spørsmål",
        required=True,
        index=True,
        tracking=True,
        help="Skrevet slik Gjermund kan svare uten å åpne noe annet. "
        "«Push Meldingssenter v1 til grenen 19.0-ports?»",
    )
    detalj = fields.Text(
        string="Grunnlag",
        help="Én linje under spørsmålet: «add-only, 0 slettinger verifisert».",
    )

    # 🤖 = AI kan utføre selv når svaret er ja · 👤 = Gjermund må gjøre det fysisk
    kilde = fields.Selection(
        [
            ("ai", "🤖 AI-økt"),
            ("menneske", "👤 Menneske-gate"),
            ("klokke", "👤 Klokke-oppgave"),
        ],
        string="Type",
        default="ai",
        required=True,
        index=True,
    )

    # Knapperaden. Fasiten har to varianter — samme kø, ulike ord.
    art = fields.Selection(
        [
            ("godkjenning", "Godkjenning (Godkjent · Ja, men… · Nei · Alltid)"),
            ("oppgave", "Oppgave til deg (Jeg gjør det · Senere · Dropp)"),
        ],
        string="Svarform",
        default="godkjenning",
        required=True,
    )

    svar = fields.Selection(
        [
            ("godkjent", "🟢 Godkjent"),
            ("ja_men", "🟠 Ja, men…"),
            ("nei", "🔴 Nei"),
            ("alltid", "🟢⭐ Alltid — slutt å spørre"),
            ("jeg_gjor", "🟢 Jeg gjør det"),
            ("senere", "🟠 Senere"),
            ("dropp", "🔴 Dropp"),
        ],
        string="Svar",
        index=True,
        tracking=True,
    )
    forbehold = fields.Text(
        string="Forbehold",
        tracking=True,
        help="«Ja, men…» uten tekst er verdiløst — økta må vite HVA forbeholdet er.",
    )

    ubesvart = fields.Boolean(
        string="Venter på deg", compute="_compute_ubesvart", store=True, index=True
    )
    haster = fields.Boolean(
        string="Haster", default=False, index=True, help="Blokkerer arbeid akkurat nå."
    )

    # ── HVEM SPØR ───────────────────────────────────────────────────────────────
    okt_id = fields.Many2one(
        "fiq.ai.okt", string="Fra økt", index=True, ondelete="set null"
    )
    spor_id = fields.Many2one(
        "fiq.ai.spor",
        string="Spor",
        index=True,
        ondelete="set null",
        help="Sporet eier spørsmålet — økta som spurte er borte om to dager.",
    )
    task_id = fields.Many2one(
        "project.task", string="Oppgave", index=True, ondelete="set null"
    )

    # 🔑 GJENTAKELSES-NØKKELEN — hele «Alltid» hviler på denne.
    # Samme nøkkel = samme SLAGS spørsmål. Svarer Gjermund «Alltid» på
    # «push_19_0_ports», svarer systemet automatisk neste gang noen spør om det samme.
    # Uten nøkkel kan «Alltid» ikke gjenkjenne noe, og knappen blir en løgn.
    noekkel = fields.Char(
        string="Gjentakelsesnøkkel",
        index=True,
        help="Teknisk nøkkel for spørsmåls-TYPEN, f.eks. «push_gren» eller "
        "«oppgrader_modul». Tom nøkkel = «Alltid» virker som «Godkjent».",
    )

    opprettet = fields.Datetime(string="Spurt", default=fields.Datetime.now, index=True)
    besvart = fields.Datetime(string="Besvart", readonly=True)
    besvart_av = fields.Many2one("res.users", string="Besvart av", readonly=True)
    company_id = fields.Many2one(
        "res.company", string="Firma", index=True, default=lambda self: self.env.company
    )

    @api.depends("svar")
    def _compute_ubesvart(self):
        for g in self:
            g.ubesvart = not g.svar

    # ── SVARING ─────────────────────────────────────────────────────────────────
    def svar_paa(self, valg, forbehold=False):
        """Gjermund svarer. «Alltid» lagres som stående regel for nøkkelen.

        `forbehold` kreves KUN på «Ja, men…» — der er den hele meningen: et ja med
        et forbehold ingen kan lese er et ja uten forbehold, og økta fortsetter
        som om det ikke fantes.
        """
        self.ensure_one()
        gyldige = dict(self._fields["svar"].selection)
        if valg not in gyldige:
            raise UserError(_("Ukjent svar: %s") % valg)
        if valg == "ja_men" and not (forbehold or "").strip():
            raise UserError(
                _(
                    "«Ja, men…» må ha et forbehold — ellers vet ikke økta hva den skal ta hensyn til."
                )
            )

        self.write(
            {
                "svar": valg,
                "forbehold": forbehold or False,
                "besvart": fields.Datetime.now(),
                "besvart_av": self.env.user.id,
            }
        )
        if valg == "alltid" and self.noekkel:
            self._lagre_staaende()
        self._varsle(gyldige[valg], forbehold)
        self._flytt_oppgaven(valg)
        return True

    # Svar → oppgaven flytter seg. Fasit 72aae7c9: «Svarer han → oppgaven flyttes
    # til I Arbeid, svaret havner i loggen.» Gjermund: «må flyttes fra et stadie til
    # neste eller blir jo listen helt statisk.»
    #
    # Et svar som ikke flytter noe, er et svar som forsvinner: spørsmålet blir
    # stående i køen og han svarer på det samme igjen i morgen.
    SVAR_TIL_STADIUM: ClassVar = {
        "godkjent": "arbeid",
        "ja_men": "arbeid",  # forbeholdet står i chatteren, arbeidet fortsetter
        "alltid": "arbeid",
        "jeg_gjor": "arbeid",
        "senere": "ko",  # tilbake i køen — ikke glemt, bare ikke nå
        "nei": "ko",
        "dropp": "ko",
    }

    def _flytt_oppgaven(self, valg):
        """Flytt oppgaven svaret gjelder. Feiler den, skal svaret STÅ.

        Svaret er det viktigste — flyttingen er en bekvemmelighet. Kaster
        stadiebyttet (manglende rettighet, slettet stadium), skal ikke Gjermunds
        svar rulles tilbake sammen med det.
        """
        self.ensure_one()
        if not self.task_id:
            return
        kode = self.SVAR_TIL_STADIUM.get(valg)
        if not kode:
            return
        try:
            with self.env.cr.savepoint():
                self.env["fiq.ai.stadie"].flytt_til(self.task_id.id, kode)
        except Exception:
            pass

    def _lagre_staaende(self):
        """«Alltid» → stående regel. Neste spørsmål med samme nøkkel svares selv.

        Lagres per firma: et ja for FIQ er ikke et ja for Vidir. Tenant-grensen
        gjelder også for tillatelser ([[fiq-kanon-tenant-isolasjon]]).
        """
        self.ensure_one()
        self.env["ir.config_parameter"].sudo().set_param(
            f"fiq_gui_ai_kr.alltid.{self.company_id.id or 0}.{self.noekkel}",
            "godkjent",
        )

    def _varsle(self, svartekst, forbehold=False):
        """Svaret i chatteren — på oppgaven hvis den finnes.

        Chatteren BÆRER, registeret peker. Samme prinsipp som konklusjons-loggen:
        én sannhet, ikke to kopier.
        """
        self.ensure_one()
        kropp = "<b>{}</b> — «{}»".format(svartekst, self.name or "")
        if forbehold:
            kropp += f"<br/><b>Forbehold:</b> {forbehold}"
        self.message_post(body=kropp)
        if self.task_id:
            self.task_id.message_post(body=kropp)

    # ── ØKTENE SPØR HER ─────────────────────────────────────────────────────────
    @api.model
    def spor(
        self,
        sporsmaal,
        detalj=False,
        kilde="ai",
        art="godkjenning",
        noekkel=False,
        spor_kode=False,
        okt_ref=False,
        task_id=False,
        haster=False,
    ):
        """En økt ber om godkjenning. Returnerer svaret HVIS det alt er gitt.

        🔑 Er det lagret et «Alltid» for nøkkelen, opprettes ingen kø-rad — økta får
        «godkjent» med én gang og kjører videre. Det er hele gevinsten: Gjermund
        svarte for tre uker siden, og spørsmålet kommer aldri tilbake.

        Returnerer: {"svar": "godkjent"|None, "id": <rad-id eller False>, "staaende": bool}
        """
        firma = self.env.company.id
        if noekkel:
            staaende = (
                self.env["ir.config_parameter"]
                .sudo()
                .get_param(f"fiq_gui_ai_kr.alltid.{firma}.{noekkel}")
            )
            if staaende == "godkjent":
                return {"svar": "godkjent", "id": False, "staaende": True}

        vals = {
            "name": sporsmaal,
            "detalj": detalj or False,
            "kilde": kilde if kilde in dict(self._fields["kilde"].selection) else "ai",
            "art": art if art in dict(self._fields["art"].selection) else "godkjenning",
            "noekkel": noekkel or False,
            "haster": bool(haster),
        }
        if task_id:
            vals["task_id"] = int(task_id)
        if spor_kode:
            vals["spor_id"] = self.env["fiq.ai.spor"]._finn_eller_lag(spor_kode).id
        if okt_ref:
            okt = self.env["fiq.ai.okt"].search([("okt_ref", "=", okt_ref)], limit=1)
            if okt:
                vals["okt_id"] = okt.id
                if not vals.get("spor_id") and okt.spor_id:
                    vals["spor_id"] = okt.spor_id.id
        rad = self.sudo().create(vals)
        return {"svar": None, "id": rad.id, "staaende": False}

    @api.model
    def hent_svar(self, godkjenning_id):
        """Økta sjekker om Gjermund har svart. Kalles før den fortsetter."""
        g = self.sudo().browse(int(godkjenning_id)).exists()
        if not g:
            return {"finnes": False}
        return {
            "finnes": True,
            "svar": g.svar or None,
            "forbehold": g.forbehold or "",
            "sporsmaal": g.name or "",
        }

    @api.model
    def staaende_regler(self, company_id=False):
        """Alle «Alltid»-svarene — så Gjermund kan se og trekke tilbake.

        En stående regel han ikke kan finne igjen, er en regel han ikke kontrollerer.
        """
        firma = int(company_id) if company_id else self.env.company.id
        prefiks = f"fiq_gui_ai_kr.alltid.{firma}."
        ut = []
        for p in (
            self.env["ir.config_parameter"]
            .sudo()
            .search([("key", "=like", prefiks + "%")])
        ):
            ut.append({"noekkel": p.key[len(prefiks) :], "verdi": p.value, "id": p.id})
        return ut

    @api.model
    def trekk_tilbake(self, noekkel, company_id=False):
        """Angre et «Alltid». Da spør systemet igjen neste gang."""
        firma = int(company_id) if company_id else self.env.company.id
        p = (
            self.env["ir.config_parameter"]
            .sudo()
            .search([("key", "=", f"fiq_gui_ai_kr.alltid.{firma}.{noekkel}")], limit=1)
        )
        if p:
            p.unlink()
            return True
        return False
