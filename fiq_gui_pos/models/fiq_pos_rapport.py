# Part of FIQ AI.
"""X- og Z-rapport etter kassasystemforskrifta § 2-8-2 og § 2-8-3.

Bokstavene a-z i feltnavnene viser til de 26 obligatoriske punktene i § 2-8-2.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FiqPosRapport(models.Model):
    _name = "fiq.pos.rapport"
    _description = "Kassarapport (X/Z) etter kassasystemforskrifta"
    _order = "dato desc, id desc"

    # --- Identifikasjon -------------------------------------------------
    name = fields.Char(string="Navn", compute="_compute_name", store=True)
    type = fields.Selection(
        [("x", "X-rapport"), ("z", "Z-rapport")],
        string="Rapporttype",
        required=True,
        readonly=True,
    )
    # § 2-8-3 (1): Z-rapport skal vere fortløpande nummerert
    nummer = fields.Integer(string="Rapportnummer", readonly=True, copy=False)
    session_id = fields.Many2one(
        "pos.session",
        string="Kassaøkt",
        required=True,
        readonly=True,
        ondelete="restrict",
    )
    config_id = fields.Many2one(
        "pos.config", string="Kassapunkt", related="session_id.config_id", store=True
    )
    company_id = fields.Many2one(
        "res.company", string="Firma", related="session_id.company_id", store=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", string="Valuta"
    )

    # § 2-8-2 b: namn og organisasjonsnummer
    firma_navn = fields.Char(string="Firmanavn", readonly=True)
    organisasjonsnummer = fields.Char(readonly=True)
    # § 2-8-2 c: dato og klokkeslett
    dato = fields.Datetime(string="Tidspunkt", readonly=True, required=True)
    # § 2-8-2 d: ID-nummer til kassapunkt
    kassapunkt_id_nummer = fields.Char(string="ID-nummer kassapunkt", readonly=True)
    fra_tidspunkt = fields.Datetime(string="Fra", readonly=True)
    # Siste ordre som inngår i rapporten. Neste X-rapport starter etter denne.
    # Brukes i stedet for tidsstempel — se _hent_ordrer().
    siste_ordre_id = fields.Integer(string="Siste ordre", readonly=True, default=0)

    # --- § 2-8-2 e-z ----------------------------------------------------
    totalt_kontantsalg = fields.Monetary(string="e) Totalt kontantsalg", readonly=True)
    antall_salg = fields.Integer(string="f) Antall salg", readonly=True)
    linje_ids = fields.One2many(
        "fiq.pos.rapport.linje", "rapport_id", string="Spesifikasjon", readonly=True
    )

    tips_antall = fields.Integer(string="i) Antall tips", readonly=True)
    tips_belop = fields.Monetary(string="i) Beløp tips", readonly=True)
    inngaende_vekselkasse = fields.Monetary(
        string="k) Inngående vekselkasse", readonly=True
    )
    antall_salgskvitteringer = fields.Integer(
        string="l) Antall salgskvitteringer", readonly=True
    )
    antall_kassaskuff_apninger = fields.Integer(
        string="m) Antall åpninger av kassaskuff", readonly=True
    )

    antall_kopikvitteringer = fields.Integer(
        string="n) Antall kopikvitteringer", readonly=True
    )
    belop_kopikvitteringer = fields.Monetary(
        string="n) Beløp kopikvitteringer", readonly=True
    )
    antall_forelopige = fields.Integer(
        string="o) Antall foreløpige kvitteringer", readonly=True
    )
    belop_forelopige = fields.Monetary(
        string="o) Beløp foreløpige kvitteringer", readonly=True
    )
    antall_returkvitteringer = fields.Integer(
        string="p) Antall returkvitteringer", readonly=True
    )
    belop_returkvitteringer = fields.Monetary(
        string="p) Beløp returkvitteringer", readonly=True
    )
    antall_rabatter = fields.Integer(string="q) Antall rabatter", readonly=True)
    belop_rabatter = fields.Monetary(string="q) Beløp rabatter", readonly=True)
    antall_avbrutte_salg = fields.Integer(
        string="r) Antall avbrutte salg", readonly=True
    )
    belop_avbrutte_salg = fields.Monetary(
        string="r) Beløp avbrutte salg", readonly=True
    )
    antall_linjekorreksjoner = fields.Integer(
        string="s) Antall linjekorreksjoner", readonly=True
    )
    antall_prisundersokelser = fields.Integer(
        string="t) Antall prisundersøkelser", readonly=True
    )
    antall_andre_korreksjoner = fields.Integer(
        string="u) Antall andre korreksjoner", readonly=True
    )
    antall_utleveringskvitteringer = fields.Integer(
        string="v) Antall utleveringskvitteringer", readonly=True
    )
    belop_utleveringskvitteringer = fields.Monetary(
        string="v) Beløp utleveringskvitteringer", readonly=True
    )
    antall_treningskvitteringer = fields.Integer(
        string="w) Antall treningskvitteringer", readonly=True
    )
    belop_treningskvitteringer = fields.Monetary(
        string="w) Beløp treningskvitteringer", readonly=True
    )

    # § 1-2 o-q: grand totals
    grand_total_salg = fields.Monetary(string="x) Grand total salg", readonly=True)
    grand_total_retur = fields.Monetary(string="y) Grand total retur", readonly=True)
    grand_total_netto = fields.Monetary(string="z) Grand total netto", readonly=True)

    # Kredittsalg og inn-/utbetalinger (§ 2-8-2 siste ledd)
    antall_kredittsalg = fields.Integer(string="Antall kredittsalg", readonly=True)
    belop_kredittsalg = fields.Monetary(string="Beløp kredittsalg", readonly=True)
    innbetalinger = fields.Monetary(readonly=True)
    utbetalinger = fields.Monetary(readonly=True)

    # § 2-8-3 (2): et Z-nummer kan ikke brukes to ganger.
    # Odoo 19 bruker models.Constraint — _sql_constraints som liste er utgått.
    _z_nummer_unikt = models.Constraint(
        "unique (company_id, type, nummer)",
        "Et Z-rapportnummer kan ikke brukes to ganger (kassasystemforskrifta § 2-8-3).",
    )

    @api.depends("type", "nummer", "config_id", "dato")
    def _compute_name(self):
        for rapport in self:
            merkelapp = _("Z-rapport") if rapport.type == "z" else _("X-rapport")
            if rapport.type == "z" and rapport.nummer:
                rapport.name = f"{merkelapp} {rapport.nummer}"
            else:
                dato = fields.Datetime.to_string(rapport.dato) or ""
                rapport.name = f"{merkelapp} {dato}"

    # --- Oppretting -----------------------------------------------------
    @api.model
    def lag_rapport(self, session, type):
        """Lag X- eller Z-rapport for en kassaøkt.

        § 2-8-3 (2): en Z-rapport kan ikke lages før alle salg er avsluttet.
        """
        if type not in ("x", "z"):
            raise UserError(_("Ukjent rapporttype."))

        if type == "z":
            aapne = self.env["pos.order"].search_count(
                [("session_id", "=", session.id), ("state", "=", "draft")]
            )
            if aapne:
                raise UserError(
                    _(
                        "Kan ikke lage Z-rapport: %s salg er ikke avsluttet. "
                        "Kassasystemforskrifta § 2-8-3 krever at alle salg er avslutta først.",
                        aapne,
                    )
                )

        verdier = self._samle_tall(session, type)
        rapport = self.create(verdier)
        rapport._lag_linjer(session)
        return rapport

    def _forrige_z(self, session):
        """Z-rapporten dekker perioden siden forrige Z (§ 1-2 m/n)."""
        return self.search(
            [
                ("config_id", "=", session.config_id.id),
                ("type", "=", "z"),
            ],
            order="nummer desc",
            limit=1,
        )

    def _hent_ordrer(self, session, type):
        """X = registreringene siden forrige Z (§ 1-2 n). Z = dagens registreringer.

        🔴 Avgrensningen skjer på ORDRE-ID, ikke på tidsstempel. Et salg som avsluttes i
        SAMME sekund som Z-rapporten ville falt ut av begge rapportene med et `date_order >`-
        filter — datofeltet har sekundoppløsning. Da ville omsetning forsvunnet stille, og
        grand totals ikke stemt. Ordre-ID er monotont økende og har ingen slik grense.
        """
        domene = [
            ("session_id", "=", session.id),
            ("state", "in", ["paid", "done", "invoiced"]),
        ]
        if type == "x":
            forrige = self._forrige_z(session)
            if forrige:
                domene.append(("id", ">", forrige.siste_ordre_id))
        return self.env["pos.order"].search(domene)

    def _samle_tall(self, session, type):
        ordrer = self._hent_ordrer(session, type)
        firma = session.company_id
        valuta = firma.currency_id

        salg = ordrer.filtered(lambda o: o.amount_total >= 0)
        retur = ordrer.filtered(lambda o: o.amount_total < 0)

        grand_salg = sum(salg.mapped("amount_total"))
        grand_retur = abs(sum(retur.mapped("amount_total")))

        rabatt_linjer = ordrer.mapped("lines").filtered(lambda linje: linje.discount)
        rabatt_belop = sum(
            (linje.price_unit * linje.qty) * (linje.discount / 100.0)
            for linje in rabatt_linjer
        )

        forrige = self._forrige_z(session)
        fra = forrige.dato if (forrige and type == "x") else session.start_at

        return {
            "type": type,
            "session_id": session.id,
            "nummer": self._neste_nummer(firma) if type == "z" else 0,
            "firma_navn": firma.name,
            "organisasjonsnummer": firma.vat or "",
            "dato": fields.Datetime.now(),
            "fra_tidspunkt": fra,
            "kassapunkt_id_nummer": session.config_id.name,
            "siste_ordre_id": max(ordrer.ids)
            if ordrer
            else (forrige.siste_ordre_id if forrige else 0),
            "totalt_kontantsalg": valuta.round(grand_salg - grand_retur),
            "antall_salg": len(ordrer),
            "antall_salgskvitteringer": len(salg),
            "antall_returkvitteringer": len(retur),
            "belop_returkvitteringer": valuta.round(grand_retur),
            "antall_rabatter": len(rabatt_linjer),
            "belop_rabatter": valuta.round(rabatt_belop),
            "inngaende_vekselkasse": session.cash_register_balance_start or 0.0,
            "grand_total_salg": valuta.round(grand_salg),
            "grand_total_retur": valuta.round(grand_retur),
            "grand_total_netto": valuta.round(grand_salg - grand_retur),
        }

    @api.model
    def _neste_nummer(self, firma):
        """Gapløs serie per firma (§ 2-8-3): ir.sequence med no_gap."""
        sekvens = (
            self.env["ir.sequence"]
            .sudo()
            .search(
                [("code", "=", "fiq.pos.rapport.z"), ("company_id", "=", firma.id)],
                limit=1,
            )
        )
        if not sekvens:
            sekvens = (
                self.env["ir.sequence"]
                .sudo()
                .create(
                    {
                        "name": _("Z-rapport %s", firma.name),
                        "code": "fiq.pos.rapport.z",
                        "implementation": "no_gap",
                        "company_id": firma.id,
                        "number_increment": 1,
                        "number_next": 1,
                        "padding": 0,
                    }
                )
            )
        return int(sekvens.next_by_id())

    def _lag_linjer(self, session):
        """f) per hovedgruppe · g) per betalingsmiddel · h) per operatør · j) per MVA-sats."""
        self.ensure_one()
        ordrer = self._hent_ordrer(session, self.type)
        Linje = self.env["fiq.pos.rapport.linje"]

        # f) hovedgrupper (produktkategori)
        pr_gruppe = {}
        for linje in ordrer.mapped("lines"):
            navn = linje.product_id.pos_categ_ids[:1].name or _("Uten gruppe")
            antall, belop = pr_gruppe.get(navn, (0, 0.0))
            pr_gruppe[navn] = (antall + 1, belop + linje.price_subtotal_incl)
        for navn, (antall, belop) in pr_gruppe.items():
            Linje.create(
                {
                    "rapport_id": self.id,
                    "kategori": "hovedgruppe",
                    "navn": navn,
                    "antall": antall,
                    "belop": belop,
                }
            )

        # g) betalingsmiddel
        pr_betaling = {}
        for betaling in ordrer.mapped("payment_ids"):
            navn = betaling.payment_method_id.name
            antall, belop = pr_betaling.get(navn, (0, 0.0))
            pr_betaling[navn] = (antall + 1, belop + betaling.amount)
        for navn, (antall, belop) in pr_betaling.items():
            Linje.create(
                {
                    "rapport_id": self.id,
                    "kategori": "betalingsmiddel",
                    "navn": navn,
                    "antall": antall,
                    "belop": belop,
                }
            )

        # h) operatør
        pr_operator = {}
        for ordre in ordrer:
            navn = ordre.user_id.name or _("Ukjent")
            antall, belop = pr_operator.get(navn, (0, 0.0))
            pr_operator[navn] = (antall + 1, belop + ordre.amount_total)
        for navn, (antall, belop) in pr_operator.items():
            Linje.create(
                {
                    "rapport_id": self.id,
                    "kategori": "operator",
                    "navn": navn,
                    "antall": antall,
                    "belop": belop,
                }
            )

        # j) avgiftspliktig/avgiftsfritt og mva fordelt på satser
        pr_sats = {}
        for linje in ordrer.mapped("lines"):
            for skatt in linje.tax_ids:
                navn = skatt.name
                antall, belop = pr_sats.get(navn, (0, 0.0))
                mva = linje.price_subtotal_incl - linje.price_subtotal
                pr_sats[navn] = (antall + 1, belop + mva)
            if not linje.tax_ids:
                navn = _("Avgiftsfritt")
                antall, belop = pr_sats.get(navn, (0, 0.0))
                pr_sats[navn] = (antall + 1, belop + linje.price_subtotal)
        for navn, (antall, belop) in pr_sats.items():
            Linje.create(
                {
                    "rapport_id": self.id,
                    "kategori": "mva",
                    "navn": navn,
                    "antall": antall,
                    "belop": belop,
                }
            )

    def unlink(self):
        """§ 2-6(2)/(3): en avgitt Z-rapport er dokumentasjon og kan ikke fjernes."""
        if any(rapport.type == "z" for rapport in self):
            # 🛑 E8140 (no-raise-unlink) er slått av MED VILJE — ikke ved et uhell.
            # OCA-regelen finnes for å hindre at sletting blokkeres av teknisk gjeld.
            # Her ER blokkeringen hele poenget: kassasystemforskrifta § 2-6 (2) og (3)
            # krever at registreringene er sikra mot sletting. Å «rette» dette ville
            # brutt et forskriftskrav for å tilfredsstille en stilregel.
            # pylint: disable=no-raise-unlink
            raise UserError(
                _(
                    "En Z-rapport kan ikke slettes. Kassasystemforskrifta krever at "
                    "registreringene er sikra mot sletting."
                )
            )
        return super().unlink()


class FiqPosRapportLinje(models.Model):
    _name = "fiq.pos.rapport.linje"
    _description = "Spesifikasjonslinje i kassarapport"
    _order = "kategori, navn"

    rapport_id = fields.Many2one(
        "fiq.pos.rapport",
        required=True,
        ondelete="cascade",
        index=True,
    )
    kategori = fields.Selection(
        [
            ("hovedgruppe", "f) Hovedgruppe"),
            ("betalingsmiddel", "g) Betalingsmiddel"),
            ("operator", "h) Operatør"),
            ("mva", "j) Merverdiavgift"),
        ],
        required=True,
    )
    navn = fields.Char(required=True)
    antall = fields.Integer()
    belop = fields.Monetary(string="Beløp")
    currency_id = fields.Many2one(
        "res.currency", related="rapport_id.currency_id", string="Valuta"
    )
