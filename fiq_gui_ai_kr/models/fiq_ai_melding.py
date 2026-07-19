# -*- coding: utf-8 -*-
"""AI-MELDINGER — all AI-kommunikasjon i én modell, to nivåer.

Gjermund 19.07.2026, ordrett:
  «alle disse meldingene mellom økter og AI roller og rådgivere skal ha sin egen
   kommunikasjonsflate i AI KR … AI-meldinger skal også være tilgjengelig som egen flate
   for alle brukere i meldingssenteret slik at alle har oversikt over sin kommunikasjon
   og forespørsler til AI»

PROBLEMET DENNE LØSER: AI-trafikken lever i dag i `brain/ai_ktrl_koordinering.md` — en fil
på over 2400 linjer som ingen bruker leser, og som Gjermund må referere manuelt. Meldinger
mellom økter, spørsmål til rådgivere og brukerens egne forespørsler er tre former for det
samme, men ingen av dem er synlige der folk faktisk jobber.

═══ TO NIVÅER, ÉN KANAL (Gjermunds valg 19.07) ═══
  • Vanlig bruker  → ser KUN sine egne forespørsler og svarene på dem
  • 000-rettighet  → ser også økt-til-økt-trafikken (drift)
Samme modell, ulik visning. Ingen duplisering, og en vanlig bruker slipper å drukne i
commit-sha-er og pin-flipp.

═══ INNHOLDSFILTRERING (Gjermunds valg 19.07) ═══
Postmesteren skiller ekte beslutningssaker fra ren videresending. Bare det første skal nå
Gjermund. `krever_svar` + `viktighet` bærer den vurderingen, og `filtrert_bort` gjør den
SYNLIG — en melding som er nedprioritert skal kunne finnes igjen, aldri forsvinne stille.
Det er hele forskjellen på filtrering og tap.
"""

from odoo import api, fields, models


class FiqAiMelding(models.Model):
    _name = "fiq.ai.melding"
    _description = "AI-melding (økt↔økt, bruker↔AI, rådgiver-forespørsel)"
    _order = "sendt desc, id desc"
    _inherit = ["mail.thread"]          # gir oss tråd, følgere og logg gratis

    name = fields.Char(string="Emne", required=True, index=True, tracking=True)
    innhold = fields.Text(string="Melding")

    # ── HVEM ────────────────────────────────────────────────────────────────────
    fra_navn = fields.Char(string="Fra", index=True,
                           help="Øktnavn, rollenavn eller personnavn. Navn — aldri ID.")
    til_navn = fields.Char(string="Til", index=True)
    fra_spor_id = fields.Many2one("fiq.ai.spor", string="Fra spor", ondelete="set null")
    til_spor_id = fields.Many2one("fiq.ai.spor", string="Til spor", ondelete="set null")
    # Brukeren meldingen GJELDER — nøkkelen til «mine forespørsler» i Meldingssenteret.
    bruker_id = fields.Many2one(
        "res.users", string="Bruker", index=True,
        help="Brukeren som spurte, eller som svaret gjelder. Tomt = ren drift mellom økter.")

    # ── HVA SLAGS ───────────────────────────────────────────────────────────────
    type_melding = fields.Selection([
        ("foresporsel", "Forespørsel til AI"),      # bruker spør
        ("svar", "Svar fra AI"),                    # AI svarer bruker
        ("okt_okt", "Økt til økt"),                 # drift: koordinering
        ("radgiver", "Rådgiver-forespørsel"),       # spørsmål til en AI-rolle
        ("beslutning", "Beslutning"),               # noe ble avgjort — skal ALDRI filtreres
        ("varsel", "Varsel"),
    ], string="Type", default="okt_okt", required=True, index=True, tracking=True)

    viktighet = fields.Selection([
        ("haster", "Haster nå"),
        ("i_dag", "Viktig i dag"),
        ("orientering", "Til orientering"),
    ], string="Viktighet", default="orientering", index=True, tracking=True)

    krever_svar = fields.Boolean(string="Krever svar", index=True, tracking=True)
    besvart = fields.Boolean(string="Besvart", tracking=True)
    # 🔴 Filtrert bort = NEDPRIORITERT, ikke slettet. Postmesteren kan ta feil, og da må
    # meldingen kunne finnes igjen. En stille filtrering er et tap forkledd som orden.
    filtrert_bort = fields.Boolean(
        string="Filtrert bort", index=True,
        help="Postmesteren vurderte den som ren videresending. Skjult som standard, "
             "men ALDRI slettet — den kan hentes fram med ett filter.")
    filtrert_grunn = fields.Char(string="Hvorfor filtrert")

    sendt = fields.Datetime(string="Sendt", default=fields.Datetime.now, index=True)
    company_id = fields.Many2one("res.company", string="Firma", index=True,
                                 default=lambda self: self.env.company)

    # Knytning til noe konkret — samme generiske mønster som sjekklista bruker.
    res_model = fields.Char(string="Gjelder (modell)", index=True)
    res_id = fields.Many2oneReference(string="Gjelder (post)", model_field="res_model", index=True)

    alder = fields.Char(string="Alder", compute="_compute_alder")

    def _compute_alder(self):
        """«12 min» / «3 t» / «2 d» — menneskelig, ikke et tidsstempel å regne på."""
        naa = fields.Datetime.now()
        for m in self:
            if not m.sendt:
                m.alder = ""
                continue
            minutter = int((naa - m.sendt).total_seconds() // 60)
            if minutter < 1:
                m.alder = "nå"
            elif minutter < 60:
                m.alder = "%d min" % minutter
            elif minutter < 60 * 24:
                m.alder = "%d t" % (minutter // 60)
            else:
                m.alder = "%d d" % (minutter // (60 * 24))

    # ── API: økter og roller fører seg selv ─────────────────────────────────────
    @api.model
    def send_ai_melding(self, name, innhold=False, fra_navn=False, til_navn=False,
                        type_melding="okt_okt", viktighet="orientering",
                        krever_svar=False, bruker_id=False, company_id=False,
                        fra_spor=False, til_spor=False, res_model=False, res_id=False):
        """Én linje for en økt/rolle å melde noe. Returnerer record-id.

        Sporene slås opp på KODE og opprettes hvis de mangler — da faller ingen melding
        utenfor bare fordi sporet ikke var registrert på forhånd.
        """
        Spor = self.env["fiq.ai.spor"]
        vals = {
            "name": name,
            "innhold": innhold or False,
            "fra_navn": fra_navn or False,
            "til_navn": til_navn or False,
            "type_melding": type_melding,
            "viktighet": viktighet,
            "krever_svar": bool(krever_svar),
            "sendt": fields.Datetime.now(),
        }
        if bruker_id:
            vals["bruker_id"] = int(bruker_id)
        if company_id:
            vals["company_id"] = int(company_id)
        if fra_spor:
            vals["fra_spor_id"] = Spor._finn_eller_lag(fra_spor).id
        if til_spor:
            vals["til_spor_id"] = Spor._finn_eller_lag(til_spor).id
        if res_model:
            vals["res_model"] = res_model
            vals["res_id"] = int(res_id) if res_id else False
        return self.sudo().create(vals).id

    def marker_besvart(self):
        """Kvitter ut en melding som krevde svar."""
        return self.write({"besvart": True})


class FiqAiMeldingData(models.AbstractModel):
    """Data-lag for AI-meldingsflaten. TO NIVÅER — samme modell, ulik visning."""
    _name = "fiq.ai.melding.data"
    _description = "AI-meldinger – data-lag (to nivåer: bruker / drift)"

    def _har_000(self):
        """000-rettighet = kryss-firma og drifts-innsyn. Fail-closed hvis KR mangler.

        Samme hjelper Kommunikasjon bruker (`fiq_gui_comm_data._har_000_rettighet`) —
        ÉN rettighetsmodell, ikke to i utakt.
        """
        KR = "fiq.gui.control.config"
        if KR in self.env and hasattr(self.env[KR], "har_000_rettighet"):
            try:
                # Savepoint: KR kan være en versjon bak i DB (manglende kolonne) → SQL-feil
                # som ellers avbryter HELE transaksjonen, ikke bare dette kallet.
                with self.env.cr.savepoint():
                    return bool(self.env[KR].har_000_rettighet())
            except Exception:
                return False   # fail-closed: uten svar gis IKKE drifts-innsyn
        return False

    @api.model
    def get_ai_meldinger(self, kun_mine=None, vis_filtrerte=False, limit=100):
        """Meldinger brukeren har lov til å se.

        🛑 SCOPE FRA SESJONEN, ALDRI FRA KLIENTEN. `kun_mine=False` gir IKKE drifts-
        trafikk til en vanlig bruker — den avgjøres av 000-rettigheten, ikke av
        parameteren. Klienten kan bare SNEVRE INN.
        """
        drift = self._har_000()
        dom = []
        # Uten 000: kun egne forespørsler/svar. MED 000: alt, men kan snevres til «mine».
        if not drift or kun_mine:
            dom.append(("bruker_id", "=", self.env.uid))
        if not vis_filtrerte:
            dom.append(("filtrert_bort", "=", False))

        out = []
        for m in self.env["fiq.ai.melding"].search(dom, order="sendt desc", limit=limit):
            out.append({
                "id": m.id,
                "emne": m.name or "",
                "innhold": m.innhold or "",
                "fra": m.fra_navn or "",
                "til": m.til_navn or "",
                "type": m.type_melding or "",
                "viktighet": m.viktighet or "",
                "krever_svar": m.krever_svar,
                "besvart": m.besvart,
                "filtrert": m.filtrert_bort,
                "filtrert_grunn": m.filtrert_grunn or "",
                "sendt": m.sendt.strftime("%d.%m %H:%M") if m.sendt else "",
                "alder": m.alder or "",
                "spor": (m.fra_spor_id.kode or m.fra_spor_id.name) if m.fra_spor_id else "",
            })
        return {"meldinger": out, "drift": drift}

    @api.model
    def get_kr_boks(self, company_id=False):
        """AI-meldinger som samleboks på KR-forsiden — «hva venter svar».

        Haster = krever svar og er ikke besvart. Det er de eneste som faktisk stopper noe.
        """
        M = self.env["fiq.ai.melding"]
        drift = self._har_000()
        grunn = [] if drift else [("bruker_id", "=", self.env.uid)]
        ubesvart = M.search(grunn + [("krever_svar", "=", True), ("besvart", "=", False),
                                     ("filtrert_bort", "=", False)], order="sendt desc")
        haster = ubesvart.filtered(lambda m: m.viktighet == "haster")
        return {
            "haster": len(haster),
            "i_dag": len(ubesvart) - len(haster),
            "totalt": M.search_count(grunn + [("filtrert_bort", "=", False)]),
            "linjer": [{"tekst": "%s — fra %s (%s)" % (m.name, m.fra_navn or "?", m.alder),
                        "res_id": m.id} for m in ubesvart[:5]],
        }
