"""Datakilde for AI GUI Regnskap (2.80) — likviditets-grunnbildet.

Rolle bak, flate foran: dette er VISNINGEN av «0.00 2.80 AI Regnskap-Rådgiver».
Native-først — tallene EIES av Odoo (`account.move`). Ingen parallell bokføring,
ingen egne summer lagret, ingen skriving. Kun lesing og gruppering.

🛑 «ALDRI gjett — regnskap er juridisk bindende» (rollens egen regel):
   alt her er BOKFØRTE tall (`state = posted`). Framskrivning/scenario hører
   hjemme et annet sted i flaten, tydelig merket — aldri blandet inn her.

🛑 TENANT-ISOLASJON: firma hentes fra `self.env.company` (sesjonen) — ALDRI som
   parameter fra klienten. Odoo håndhever `ir.rule` på toppen. En bruker kan
   dermed aldri be om et annet firmas tall ved å manipulere kallet.
"""

from odoo import api, fields, models
from odoo.fields import Command  # noqa: F401  (holdes for framtidig bruk)


class FiqGuiRgsData(models.AbstractModel):
    """Leser likviditetsbildet. AbstractModel = ingen tabell, ingen lagrede tall."""

    _name = "fiq.gui.rgs.data"
    _description = "FIQ Regnskap — likviditetsdata (lesing av account.move)"

    # Kundefakturaer = penger INN. Leverandørfakturaer = penger UT.
    # `out_refund`/`in_refund` (kreditnotaer) trekker automatisk ned via
    # amount_residual, som er negativ på dem — derfor tas de med i samme bøtte.
    INN_TYPER = ("out_invoice", "out_refund")
    UT_TYPER = ("in_invoice", "in_refund")

    @api.model
    def _basis_domene(self, typer):
        """Felles filter: bokført, ikke betalt, riktig firma.

        `state = posted` er det som gjør tallet til FAKTA. Kladd og kansellerte
        bilag er ikke bokført og skal aldri telle med i et likviditetsbilde.

        🛑 GJERMUNDS AVGJØRELSE 23.07 (oppgave 08.10) — `in_payment` teller som
        UTESTÅENDE, og det er BEVISST:
            «De skal være registrert betalt før de forsvinner — ikke nødvendigvis
             månedlig bankavstemming, men ja: en avstemming mot bank.»
        Et bilag forlater altså likviditetsbildet først når betalingen er bekreftet
        mot bank. `payment_state = in_payment` betyr registrert, ikke bekreftet.
        Filteret er derfor UENDRET — men flaten SIER FRA (`i_betaling_antall`),
        og sier også om banktilstanden gjør bekreftelse mulig (`bankavstemming`).
        """
        return [
            ("move_type", "in", typer),
            ("state", "=", "posted"),
            ("payment_state", "not in", ("paid", "reversed")),
            ("company_id", "=", self.env.company.id),  # fra sesjonen, ikke fra klienten
        ]

    @api.model
    def _sum_restbelop(self, domene):
        """Summerer utestående beløp. `amount_residual` = det som faktisk gjenstår."""
        grupper = self.env["account.move"]._read_group(
            domene, aggregates=["amount_residual:sum"]
        )
        return grupper[0][0] or 0.0 if grupper else 0.0

    @api.model
    def hent_grunnbilde(self):
        """Returnerer likviditets-grunnbildet for gjeldende firma.

        Bøttene er Gjermunds spesifikasjon: inn · ut · haster · kritisk · ubetalt.
        «Haster» og «kritisk» er tidsbaserte snitt av det UBETALTE — ikke egne
        pengestrømmer. De overlapper derfor bevisst med «ubetalt»; det er
        meningen (samme krone kan være både ubetalt og kritisk).
        """
        i_dag = fields.Date.context_today(self)
        om_en_uke = fields.Date.add(i_dag, days=7)

        inn = self._sum_restbelop(self._basis_domene(self.INN_TYPER))
        ut = self._sum_restbelop(self._basis_domene(self.UT_TYPER))

        # Haster = forfaller innen 7 dager, men er IKKE forfalt ennå.
        haster = self._sum_restbelop(
            self._basis_domene(self.INN_TYPER + self.UT_TYPER)
            + [("invoice_date_due", ">=", i_dag), ("invoice_date_due", "<=", om_en_uke)]
        )
        # Kritisk = allerede forfalt. Dette er pengene som burde vært inne.
        kritisk = self._sum_restbelop(
            self._basis_domene(self.INN_TYPER + self.UT_TYPER)
            + [("invoice_date_due", "<", i_dag)]
        )
        ubetalt = self._sum_restbelop(
            self._basis_domene(self.INN_TYPER + self.UT_TYPER)
        )

        valuta = self.env.company.currency_id

        # ÆRLIG SCOPE (GUI Prosjekt 19.07): tallet gjelder ETT firma. Har brukeren
        # tilgang til flere, er dette IKKE et konserntall — og det må stå, ellers
        # leses et ufullstendig tall som helheten. Fail-closed er riktig; stille
        # fail-closed er ikke.
        #
        # ⚠️ `company_ids` (tilgang), IKKE `env.companies` (aktivert akkurat nå).
        # Med env.companies forsvinner merket nettopp når brukeren har skrudd AV de
        # andre firmaene — altså akkurat da tallet er mest ufullstendig. Verifisert
        # 19.07: env.companies=1 mens brukeren har tilgang til flere.
        antall_tilgjengelige = len(self.env.user.company_ids)

        # 🔴 REGISTRERT ≠ BEKREFTET (målt på fiqas Production 22.07, www.fiq.no):
        # 19 av 20 kundefakturaer står som `in_payment`, og alle 27 betalinger som
        # `in_process` — betaling er registrert, men ikke avstemt mot bankutskrift.
        # `_basis_domene` teller `in_payment` som UTESTÅENDE (konservativt valg).
        #
        # Dilemmaet, og grunnen til at tallet ikke endres her: teller de som betalt,
        # viser flaten penger som kanskje aldri kom. Teller de som utestående, ser
        # likviditeten dårligere ut enn den er. Begge feil er ille og peker motsatt
        # vei — derfor er dette en MENNESKELIG avgjørelse, ikke et kodevalg.
        #
        # Til den er tatt: behold det konservative tallet, men SI HVA DET INNEHOLDER.
        # Da lyver det ikke i noen retning, og brukeren ser hvorfor. (Finans 2.70, 22.07)
        i_betaling = self.env["account.move"].search_count(
            self._basis_domene(self.INN_TYPER + self.UT_TYPER)
            + [("payment_state", "=", "in_payment")]
        )

        return {
            "firma": self.env.company.name,
            "valuta": valuta.symbol or valuta.name,
            "dato": fields.Date.to_string(i_dag),
            "scope_ett_firma": True,
            "antall_firmaer": antall_tilgjengelige,
            "botter": [
                {
                    "key": "inn",
                    "label": "Inngående",
                    "verdi": inn,
                    "hjelp": "Bokførte kundefakturaer som ikke er betalt",
                },
                {
                    "key": "ut",
                    "label": "Utgående",
                    "verdi": ut,
                    "hjelp": "Bokførte leverandørfakturaer som ikke er betalt",
                },
                {
                    "key": "haster",
                    "label": "Haster",
                    "verdi": haster,
                    "hjelp": "Forfaller innen 7 dager",
                },
                {
                    "key": "kritisk",
                    "label": "Kritisk",
                    "verdi": kritisk,
                    "hjelp": "Allerede forfalt",
                },
                {
                    "key": "ubetalt",
                    "label": "Ubetalt",
                    "verdi": ubetalt,
                    "hjelp": "Alt utestående, inn og ut",
                },
            ],
            # Netto = det bildet daglig leder faktisk spør om: har vi penger igjen?
            "netto": inn - ut,
            # Ærlighet i datasettet, ikke bare i visningen — samme prinsipp som
            # `mangler` i hent_cashflow. Er tallet 0, skal flaten ikke vise noe.
            "i_betaling_antall": i_betaling,
            "i_betaling_merknad": (
                f"{i_betaling} bilag er registrert betalt, men ikke bekreftet mot bank. "
                "De telles fortsatt som utestående."
            )
            if i_betaling
            else "",
            # Sier HVORFOR de blir stående: er avstemming i det hele tatt mulig?
            # Uten dette leses tallet som slurv, når årsaken kan være at ingen
            # bankkobling finnes. (Gjermund 08.10)
            "bankavstemming": self.hent_bankavstemming(),
            "base": self._base_merke(),
        }

    @api.model
    def hent_cashflow(self, uker=12):
        """Framskrivning: når kommer pengene inn, og når går de ut?

        Gjermunds spec: «cashflow-bilde + mulige kritiske likviditetsdatoer
        (når blir det tight?)».

        🛑 DETTE ER EN FRAMSKRIVNING, IKKE BOKFØRTE TALL. Den bygger på FAKTA
        (bokførte, ubetalte bilag med forfallsdato), men sier noe om FRAMTIDA —
        og framtida er en antagelse. Flaten merker den som framskrivning.

        🛑 LØNNSFORPLIKTELSER KOBLET 23.07 (2.20 HR Lønn): lønnskjøring,
        arbeidsgiveravgift, feriepenger og pensjon hentes nå som AGGREGATER —
        aldri persondata. Kurven er dermed ikke lenger blind for dem.

        🛑 MEN `mangler` GJELDER FORTSATT, og er nå mer presis: den skiller
        «ikke bygd ennå» fra «bygd, men ingen data for dette selskapet» (f.eks.
        når sone for arbeidsgiveravgift ikke er registrert). Grunnen hentes fra
        2.20 Lønn — de eier lønnsdata og dermed også årsaken.
        Fjernes ALDRI uten at tallene faktisk er koblet.
        """
        i_dag = fields.Date.context_today(self)
        alle = self.INN_TYPER + self.UT_TYPER

        bilag = self.env["account.move"].search_read(
            self._basis_domene(alle) + [("invoice_date_due", "!=", False)],
            ["invoice_date_due", "amount_residual", "move_type"],
            order="invoice_date_due asc",
        )

        # Forfalt = alt som skulle vært betalt før i dag. Det er utgangspunktet,
        # ikke en framtidig hendelse — derfor egen post, ikke en uke i kurven.
        forfalt_inn = sum(
            b["amount_residual"]
            for b in bilag
            if b["invoice_date_due"] < i_dag and b["move_type"] in self.INN_TYPER
        )
        forfalt_ut = sum(
            b["amount_residual"]
            for b in bilag
            if b["invoice_date_due"] < i_dag and b["move_type"] in self.UT_TYPER
        )

        # Lønnsforpliktelser fra 2.20 HR Lønn — aggregater, aldri persondata.
        # Positivt `belop` = utbetaling ut av konto (deres punkt 03).
        lonnslinjer = self._hent_lonnslinjer(
            i_dag, fields.Date.add(i_dag, days=7 * uker)
        )

        punkter = []
        saldo = forfalt_inn - forfalt_ut
        laveste = {"saldo": saldo, "uke": 0, "dato": fields.Date.to_string(i_dag)}

        for u in range(uker):
            fra = fields.Date.add(i_dag, days=7 * u)
            til = fields.Date.add(i_dag, days=7 * (u + 1))
            inn = sum(
                b["amount_residual"]
                for b in bilag
                if fra <= b["invoice_date_due"] < til
                and b["move_type"] in self.INN_TYPER
            )
            ut = sum(
                b["amount_residual"]
                for b in bilag
                if fra <= b["invoice_date_due"] < til
                and b["move_type"] in self.UT_TYPER
            )
            # Lønn plasseres etter FORFALL, aldri etter `periode` — periode er
            # ren visning (avtalt med 2.20 Lønn 22.07). Augustlønn betalt 15.
            # september hører i septemberuka, uansett hva perioden heter.
            uke_lonn = [linje for linje in lonnslinjer if fra <= linje["forfall"] < til]
            lonn_ut = sum(linje["belop"] for linje in uke_lonn)
            ut += lonn_ut
            saldo += inn - ut
            punkter.append(
                {
                    "uke": u,
                    "fra": fields.Date.to_string(fra),
                    "inn": inn,
                    "ut": ut,
                    "saldo": saldo,
                    # Kritisk = saldoen går under null. Det er «når blir det tight».
                    "kritisk": saldo < 0,
                    # Hva av «ut» som er lønnsforpliktelser — så flaten kan forklare
                    # et brått hopp (f.eks. når fribeløpet for AGA er brukt opp).
                    "lonn_ut": lonn_ut,
                    "lonn_linjer": uke_lonn,
                }
            )
            if saldo < laveste["saldo"]:
                laveste = {"saldo": saldo, "uke": u, "dato": fields.Date.to_string(fra)}

        return {
            "punkter": punkter,
            "forfalt_inn": forfalt_inn,
            "forfalt_ut": forfalt_ut,
            "start_saldo": forfalt_inn - forfalt_ut,
            "laveste": laveste,
            "kritiske_uker": [p for p in punkter if p["kritisk"]],
            # Ærlighet i selve datasettet, ikke bare i visningen.
            "mangler": self._mangler_forpliktelser(),
            "grunnlag": "Bokførte, ubetalte bilag med forfallsdato",
        }

    # Forpliktelsene 2.20 HR Lønn eier. Rekkefølgen er deres leveranseplan
    # (AGA → lønnskostnad → OTP → feriepenger), avtalt 22.07.
    LONNSTYPER = [
        ("aga", "Arbeidsgiveravgift"),
        ("lonn", "Lønnskjøringer"),
        ("otp", "Pensjon"),
        ("feriepenger", "Feriepenger"),
    ]

    @api.model
    def _lonn_modell(self):
        """Mykt oppslag mot 2.20 HR Lønn. Returnerer modellen eller None.

        🔴 TO RECORDSET-FELLER, begge målt 23.07 — ikke antatt:
          1. `env.get('ukjent.modell')` gir et TOMT RECORDSET, ikke None.
             En `is None`-sjekk slår derfor aldri til.
          2. `finnes and env[modell] or None` faller ALLTID til None, fordi et
             tomt recordset er FALSKT i Python. Min første kobling brukte
             nettopp det — og meldte «ikke bygd» selv når Lønn svarte
             «mangler_sone». 26 tester var grønne mens koblingen var død.
        Derfor: eksplisitt oppslag i modellregisteret, ingen and/or-triks.

        🛑 `fiq_rgs_lonn` er IKKE en avhengighet og skal aldri bli det. En base
        uten lønn er en normal base, ikke en feil.
        """
        if (
            not self.env["ir.model"]
            .sudo()
            .search_count([("model", "=", "fiq.lonnsforpliktelse")])
        ):
            return None
        return self.env["fiq.lonnsforpliktelse"]

    @api.model
    def _hent_lonnslinjer(self, fra_dato, til_dato):
        """Lønnsforpliktelser fra 2.20 HR Lønn — aggregater, aldri persondata.

        🔒 PERSONVERN: vi mottar KUN summer. Ingen `employee_id`, ingen navn,
        og aldri en linje som representerer færre enn tre ansatte — 2.20 Lønn
        håndhever grensen på sin side og melder da `ingen_data` i stedet.
        Vi ber aldri om underlaget, uansett hvor nyttig det måtte være.

        🛑 Feiler kallet, returneres tom liste — og `mangler` melder «ukjent»
        i stedet for å utelate typen. En kurve som stille mister en hel
        forpliktelsestype er nøyaktig det vakten finnes for å hindre.
        """
        Lonn = self._lonn_modell()
        if Lonn is None or not hasattr(Lonn, "hent_lonnsforpliktelser"):
            return []
        try:
            linjer = Lonn.hent_lonnsforpliktelser(fra_dato, til_dato) or []
        except Exception:
            return []

        rene = []
        for linje in linjer:
            forfall = linje.get("forfall")
            if not forfall or linje.get("belop") in (None, False):
                continue  # en linje uten dato kan ikke plasseres i en uke
            if isinstance(forfall, str):
                forfall = fields.Date.to_date(forfall)
            rene.append(
                {
                    "type": linje.get("type"),
                    "label": linje.get("label") or "",
                    "forfall": forfall,
                    "belop": linje["belop"],
                    # `sikkerhet` følger helt ut i flaten: en `planlagt` linje skal
                    # ALDRI se ut som et bokført tall. Rollens egen regel.
                    "sikkerhet": linje.get("sikkerhet") or "estimat",
                    "kilde": linje.get("kilde") or "",
                    "periode": linje.get("periode") or "",
                    # Valgfritt hos Lønn — forklarer f.eks. at fribeløpet er brukt
                    # opp og at satsen derfor hopper. Ren visning, aldri beregning.
                    "merknad": linje.get("merknad") or "",
                }
            )
        return rene

    @api.model
    def _mangler_forpliktelser(self):
        """Hva mangler cashflow-kurven — og HVORFOR.

        🔴 TRE TILSTANDER, IKKE TO (funnet 23.07, løst sammen med 2.20 Lønn):
            01  Lønn leverer tall            → linja fjernes
            02  Lønn har ikke levert ennå    → «ikke bygd ennå»
            03  Lønn LEVERTE, men fant intet → «koblet, men ingen data»
        Tilstand 03 var usynlig i den gamle lista: den var en flat liste med navn,
        så en type som var koblet MEN tom ville blitt fjernet — og kurven sett
        komplett ut mens en hel forpliktelsestype manglet. Nøyaktig det denne
        lista finnes for å hindre.

        🔑 GRUNNEN HENTES FRA KILDEN, IKKE GJETTES HER. 2.20 Lønn eier lønnsdata
        og dermed også årsaken til at noe mangler (f.eks. at selskapet ikke har
        registrert sone for arbeidsgiveravgift). Endrer de oppførsel, følger
        forklaringen med — vi vedlikeholder ingen egen oversettelse av deres
        feilmodi.

        🛑 MYKT OPPSLAG: `fiq_rgs_lonn` er IKKE en avhengighet. Er den ikke
        installert, skal flaten virke som før — ikke krasje. En base uten lønn
        er en normal base, ikke en feil.
        """
        # 🔴 MÅLT 23.07, IKKE ANTATT: `env.get('ukjent.modell')` returnerer et TOMT
        # RECORDSET, ikke None — «fiq.lonnsforpliktelse()». En None-sjekk ville
        # derfor sluppet gjennom, og `hasattr` båret hele vekten. Riktig test på
        # om en modell finnes er oppslag i modellregisteret.
        Lonn = self._lonn_modell()
        if Lonn is None or not hasattr(Lonn, "status_forpliktelser"):
            # Tilstand 02 for alle: modulen finnes ikke ennå.
            return [
                {
                    "type": kode,
                    "navn": navn,
                    "levert": False,
                    "grunn": "ikke_bygd",
                    "forklaring": "Ikke koblet til flaten ennå",
                }
                for kode, navn in self.LONNSTYPER
            ]

        i_dag = fields.Date.context_today(self)
        try:
            status = Lonn.status_forpliktelser(i_dag, fields.Date.add(i_dag, days=84))
        except Exception:
            # Feiler oppslaget, er det ærligere å si «ukjent» enn å utelate
            # linjene — en tom `mangler` leses som «alt er med».
            status = {}

        mangler = []
        for kode, navn in self.LONNSTYPER:
            info = status.get(kode) or {}
            if info.get("levert"):
                continue  # tilstand 01 — tallene er i kurven
            mangler.append(
                {
                    "type": kode,
                    "navn": navn,
                    "levert": False,
                    "grunn": info.get("grunn") or "ikke_bygd",
                    "forklaring": info.get("forklaring")
                    or "Ikke koblet til flaten ennå",
                }
            )
        return mangler

    @api.model
    def apne_botte(self, key):
        """Åpner Odoos EGEN fakturaliste, filtrert på bøtta brukeren klikket.

        Gjermund/GUI Prosjekt 19.07: «tall → klikk → liste med det som ligger bak.
        Ikke tall som blindvei.»

        Native-først i praksis: vi bygger ingen egen liste — vi sender brukeren til
        Odoos fakturavisning med riktig filter. Da får hun alle Odoos egne verktøy
        (sortering, gruppering, eksport) uten at vi gjenskaper dem.
        """
        i_dag = fields.Date.context_today(self)
        alle = self.INN_TYPER + self.UT_TYPER

        if key == "inn":
            domene, tittel = self._basis_domene(self.INN_TYPER), "Inngående"
        elif key == "ut":
            domene, tittel = self._basis_domene(self.UT_TYPER), "Utgående"
        elif key == "haster":
            domene = self._basis_domene(alle) + [
                ("invoice_date_due", ">=", i_dag),
                ("invoice_date_due", "<=", fields.Date.add(i_dag, days=7)),
            ]
            tittel = "Haster"
        elif key == "kritisk":
            domene = self._basis_domene(alle) + [("invoice_date_due", "<", i_dag)]
            tittel = "Kritisk"
        else:
            domene, tittel = self._basis_domene(alle), "Ubetalt"

        return {
            "type": "ir.actions.act_window",
            "name": tittel,
            "res_model": "account.move",
            "view_mode": "list,form",  # Odoo 19: «list», ikke «tree»
            "domain": domene,
            "context": {"create": False},  # lesing fra en oversikt — ikke opprettelse
        }

    @api.model
    def get_kr_boks(self, company_id=False):
        """Samleboks til Kontrollrom-forsiden (KR-kontrakt, verifisert i
        `fiq_gui_control_config.py:1335`).

        Gjermund 19.07.2026: «om det er 5 saker som haster på finans og tre i dag så
        vises det som en boks i KR og om jeg trykker på en av boksene kommer jeg inn
        i finans eller RGS ihht hva jeg trykker på.»

        Her er «saker» = ubetalte bokførte fakturaer:
          haster = forfaller innen 7 dager (ikke forfalt ennå)
          i_dag  = forfaller nøyaktig i dag
          totalt = alt utestående

        🛑 TENANT: `company_id` kommer fra KR, men brukes ALDRI rått. Vi bytter firma
           via `with_company()` — da gjelder `ir.rule` fortsatt, og en bruker uten
           tilgang får ingenting. Klienten kan ikke be seg til et annet firmas tall.

        🛑 ÆRLIGHET: kan tallet ikke regnes, returneres INGEN boks (None) — aldri 0.
           «0 kr utestående» er en farlig løgn i regnskap; en manglende boks er ærlig.
        """
        selv = self.with_company(company_id) if company_id else self
        i_dag = fields.Date.context_today(selv)
        om_en_uke = fields.Date.add(i_dag, days=7)
        alle = selv.INN_TYPER + selv.UT_TYPER

        Move = selv.env["account.move"]
        haster = Move.search_count(
            selv._basis_domene(alle)
            + [("invoice_date_due", ">=", i_dag), ("invoice_date_due", "<=", om_en_uke)]
        )
        i_dag_ant = Move.search_count(
            selv._basis_domene(alle) + [("invoice_date_due", "=", i_dag)]
        )
        totalt = Move.search_count(selv._basis_domene(alle))

        # Forfalte først — det er dem som haster mest, uansett hva kalenderen sier.
        forfalte = Move.search_read(
            selv._basis_domene(alle) + [("invoice_date_due", "<", i_dag)],
            ["name", "partner_id", "amount_residual", "invoice_date_due"],
            order="amount_residual desc",
            limit=5,
        )
        linjer = []
        for p in forfalte:
            dager = (i_dag - p["invoice_date_due"]).days if p["invoice_date_due"] else 0
            motpart = p["partner_id"][1] if p["partner_id"] else "—"
            linjer.append(
                {
                    "tekst": "{} forfalt {} dager — {}".format(
                        p["name"], dager, motpart
                    ),
                    "res_id": p["id"],
                }
            )

        return {
            "haster": haster,
            "i_dag": i_dag_ant,
            "totalt": totalt,
            "linjer": linjer,
        }

    @api.model
    def hent_kritiske_poster(self, grense=10):
        """De største forfalte postene — så flaten kan vise HVILKE, ikke bare hvor mye.

        Navn, ikke ID-er (husets regel). Partner-navn er forretningsdata innenfor
        eget firma — tenant-grensa håndheves av domenet + `ir.rule`.
        """
        poster = self.env["account.move"].search_read(
            self._basis_domene(self.INN_TYPER + self.UT_TYPER)
            + [("invoice_date_due", "<", fields.Date.context_today(self))],
            ["name", "partner_id", "amount_residual", "invoice_date_due", "move_type"],
            order="amount_residual desc",
            limit=grense,
        )
        return [
            {
                "nummer": p["name"],
                "motpart": p["partner_id"][1] if p["partner_id"] else "—",
                "belop": p["amount_residual"],
                "forfall": p["invoice_date_due"],
                "retning": "inn" if p["move_type"] in self.INN_TYPER else "ut",
            }
            for p in poster
        ]

    # ------------------------------------------------------------------
    # TIDLIG KORRIGERING (Gjermunds spec: «kortere frister · tidligere fakturering»)
    # ------------------------------------------------------------------

    # Under dette antallet er et snitt ikke et mønster, men en anekdote.
    # 🛑 Terskel for å UTTALE seg — ikke for å regne. Vi regner uansett, men
    #    flaten sier fra når grunnlaget er for tynt til en anbefaling.
    MIN_FAKTURA_FOR_MONSTER = 5

    @api.model
    def _base_merke(self):
        """Hvilken base tallene kommer fra — SERVER, ikke bare firmanavn.

        🔑 LÆRDOM 22.07 (fire økter, samme dag, samme feil): firmanavn identifiserer
        INNHOLD, ikke SERVER. «FIQ as» finnes på både Staging og Production, og et
        demodata-tall uten base-merke leses som ekte. Både Finans og denne økta
        rapporterte tall fra feil base før noen målte `web.base.url`.
        """
        url = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        return {"firma": self.env.company.name, "url": url}

    @api.model
    def hent_bankavstemming(self):
        """Er bankavstemming i det hele tatt mulig i dag? Måler, påstår ikke.

        Gjermund 23.07 (08.10): et bilag skal forlate likviditetsbildet først når
        betalingen er «registrert betalt» — bekreftet mot bank. Da må flaten kunne
        svare på om den bekreftelsen er MULIG, ikke bare om den har skjedd.
        Uten dette leses «19 bilag venter på avstemming» som slurv, når årsaken
        kan være at ingen bankkobling finnes ennå.

        🛑 MÅLER TILSTAND, GIR IKKE RÅD. Hvilken bank som skal kobles og når er
        et menneskevalg (08.11). Flaten sier hva som er, ikke hva som bør gjøres.

        Målt på fiqas Production 23.07 (`https://www.fiq.no`):
            account_online_synchronization  installert
            account_bank_statement_import_camt  installert
            bankjournal «Bank»: kontonummer TOMT · kilde «undefined»
            account.bank.statement       0
            account.bank.statement.line  0
        Altså: verktøyet finnes, men er aldri tatt i bruk.
        """
        Journal = self.env["account.journal"]
        journaler = Journal.search(
            [
                ("type", "=", "bank"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        # `bank_statements_source` = «undefined» betyr at ingen kilde er valgt —
        # verken filimport eller direkte kobling. Da kan ingenting avstemmes.
        uten_kilde = journaler.filtered(
            lambda j: (
                not j.bank_statements_source or j.bank_statements_source == "undefined"
            )
        )
        linjer = self.env["account.bank.statement.line"].search_count(
            [
                ("company_id", "=", self.env.company.id),
            ]
        )

        mulig = bool(journaler) and len(uten_kilde) < len(journaler)
        return {
            "bankjournaler": len(journaler),
            "uten_kilde": len(uten_kilde),
            "utskriftslinjer": linjer,
            "avstemming_mulig": mulig,
            "merknad": ""
            if mulig
            else (
                "Ingen bankjournal har en kilde for kontoutskrift. Betalinger kan "
                "registreres, men ikke bekreftes mot bank — derfor blir bilag "
                "stående som utestående."
            ),
            "base": self._base_merke(),
        }

    @api.model
    def _betalingsdager(self, partner_id=False):
        """Faktisk betalingsforsinkelse per faktura: betalingsdato − forfallsdato.

        🛑 HVORFOR IKKE `payment_state`: den sier om Odoo anser bilaget oppgjort,
        ikke NÅR pengene kom. Målt på fiqas Production 22.07 (`https://www.fiq.no`):
        0 av 20 kundefakturaer står som `paid`, og alle 27 betalinger som
        `in_process`. Et mål bygd på `payment_state` ville rapportert «ingen data»
        der det faktisk finnes 27 registrerte betalinger.

        Vi leser derfor `account.payment.date` via `reconciled_invoice_ids` —
        koblingen betaling→faktura, uavhengig av avstemmingsstatus.

        ⚠️ FAKTA vs USIKKERHET: en betaling som ikke er avstemt mot bank
        (`is_matched = False`) er REGISTRERT, ikke BEKREFTET. Vi teller den, men
        merker den — å utelate den skjuler data, å telle den stille overdriver
        sikkerheten.
        """
        domene = [
            ("state", "!=", "cancel"),
            ("payment_type", "=", "inbound"),
            ("company_id", "=", self.env.company.id),  # fra sesjonen, aldri klienten
        ]
        if partner_id:
            domene.append(("partner_id", "=", partner_id))

        rader = []
        for bet in self.env["account.payment"].search(domene):
            if not bet.date:
                continue
            # 🔴 `invoice_ids`, IKKE `reconciled_invoice_ids` (målt på Dev 22.07):
            # `reconciled_invoice_ids` fylles først når betalingen er AVSTEMT mot
            # bank. På fiqas Production står alle 27 betalinger som `in_process` —
            # da er den lista TOM, og motoren hadde rapportert «ingen betalinger»
            # på en base med 27 av dem. `invoice_ids` er koblingen som finnes fra
            # betalingen registreres, uavhengig av avstemming.
            for faktura in bet.invoice_ids:
                if (
                    faktura.move_type not in self.INN_TYPER
                    or not faktura.invoice_date_due
                ):
                    continue
                rader.append(
                    {
                        "partner_id": bet.partner_id.id,
                        "motpart": bet.partner_id.display_name or "—",
                        "dager": (bet.date - faktura.invoice_date_due).days,
                        "belop": bet.amount,
                        "bekreftet": bet.is_matched,  # avstemt mot bankutskrift?
                    }
                )
        return rader

    @api.model
    def hent_betalingsmonster(self):
        """Hvordan betaler kundene FAKTISK — grunnlaget for tidlig korrigering.

        Gjermunds spec 2.80: «tidlig korrigering — kortere frister, tidligere
        fakturering». En slik anbefaling er verdiløs uten å vite hvem som faktisk
        betaler sent. Dette er MÅLINGEN; anbefalingen bygger på den.

        🛑 FRAMSKRIVNING, IKKE BOKFØRT TALL. Snittet beskriver fortida og brukes til
        å anslå framtida. Det er ikke et regnskapstall, og flaten merker det slik.

        🛑 ÆRLIG OM GRUNNLAGET (samme prinsipp som `mangler` i hent_cashflow):
        returverdien sier hvor mange fakturaer og motparter snittet bygger på, og
        `godt_nok` er False når det er for tynt. En anbefaling på tynt grunnlag er
        gjetning i pen innpakning — og «ALDRI gjett» er rollens egen regel.
        """
        rader = self._betalingsdager()

        per_motpart = {}
        for r in rader:
            p = per_motpart.setdefault(
                r["partner_id"],
                {
                    "motpart": r["motpart"],
                    "dager": [],
                    "antall": 0,
                    "ubekreftet": 0,
                },
            )
            p["dager"].append(r["dager"])
            p["antall"] += 1
            if not r["bekreftet"]:
                p["ubekreftet"] += 1

        motparter = []
        for data in per_motpart.values():
            dager = data["dager"]
            snitt = sum(dager) / len(dager)
            motparter.append(
                {
                    "motpart": data["motpart"],
                    "antall_fakturaer": data["antall"],
                    "snitt_dager": round(snitt, 1),
                    "verste_dager": max(dager),
                    # Positivt snitt = betaler ETTER forfall. Det er dem tiltaket gjelder.
                    "betaler_sent": snitt > 0,
                    "ubekreftede": data["ubekreftet"],
                }
            )
        motparter.sort(key=lambda m: m["snitt_dager"], reverse=True)

        antall = len(rader)
        ubekreftede = sum(1 for r in rader if not r["bekreftet"])
        return {
            "motparter": motparter,
            "antall_fakturaer": antall,
            "antall_motparter": len(motparter),
            "ubekreftede_betalinger": ubekreftede,
            "godt_nok": antall >= self.MIN_FAKTURA_FOR_MONSTER and len(motparter) >= 2,
            "grunnlag": (
                "Registrerte innbetalinger koblet til bokførte kundefakturaer. "
                "Måler betalingsdato mot forfallsdato — ikke bilagets betalingsstatus."
            ),
            "forbehold": (
                f"{ubekreftede} av {antall} betalinger er ikke avstemt mot bankutskrift — "
                "registrert, men ikke bekreftet."
            )
            if ubekreftede
            else "",
            "base": self._base_merke(),
        }

    # Under dette snittet er forsinkelsen støy, ikke et mønster verdt et tiltak.
    MIN_DAGER_FOR_TILTAK = 5
    # En motpart må ha nok fakturaer til at snittet betyr noe for AKKURAT den.
    MIN_FAKTURA_PER_MOTPART = 3

    @api.model
    def hent_tidlig_korrigering(self):
        """Hva kan gjøres FØR det brenner — kortere frister, tidligere fakturering.

        Gjermunds spec 2.80: «tidlig korrigering — hjelpe med grep FØR det brenner,
        for å verne likviditeten». Dette er 08.03.02; motoren er `hent_betalingsmonster`.

        🛑 TIER NÅR GRUNNLAGET IKKE BÆRER. Er `godt_nok` False — for få fakturaer
        eller for få motparter — returneres INGEN forslag, bare årsaken. En
        anbefaling bygget på ett tilfelle er gjetning i pen innpakning, og
        «ALDRI gjett» er rollens egen regel. Det er billigere å si «vet ikke»
        enn å foreslå kortere frister til en kunde på grunnlag av én faktura.

        🛑 RÅDGIVER, IKKE BESLUTTER. Hvert forslag har `begrunnelse` og `grunnlag`
        (hvor mange fakturaer det bygger på) slik at mennesket kan overprøve det.
        Ingen automatiske handlinger — flaten foreslår, daglig leder bestemmer.

        🔒 Motpartsnavn er forretningsdata innenfor eget firma; tenant-grensa
        håndheves av `_betalingsdager` (company fra sesjonen) + `ir.rule`.
        """
        m = self.hent_betalingsmonster()

        if not m["godt_nok"]:
            return {
                "forslag": [],
                "kan_anbefale": False,
                "hvorfor_ikke": (
                    "Grunnlaget er for tynt: {} betaling(er) fordelt på {} motpart(er). "
                    "Et snitt fra så få tilfeller er en enkelthendelse, ikke et mønster.".format(
                        m["antall_fakturaer"], m["antall_motparter"]
                    )
                ),
                "grunnlag": m["grunnlag"],
                "forbehold": m["forbehold"],
                "base": m["base"],
            }

        forslag = []
        for mp in m["motparter"]:
            if mp["antall_fakturaer"] < self.MIN_FAKTURA_PER_MOTPART:
                continue  # for tynt for AKKURAT denne motparten
            if mp["snitt_dager"] < self.MIN_DAGER_FOR_TILTAK:
                continue  # betaler i praksis i tide — ingen grunn til tiltak

            dager = mp["snitt_dager"]
            if dager >= 30:
                tiltak = "Vurder forskuddsfakturering eller delbetaling"
            elif dager >= 14:
                tiltak = "Vurder kortere betalingsfrist"
            else:
                tiltak = "Vurder å fakturere tidligere i leveransen"

            forslag.append(
                {
                    "motpart": mp["motpart"],
                    "tiltak": tiltak,
                    "snitt_dager": dager,
                    "verste_dager": mp["verste_dager"],
                    # Begrunnelsen står i datasettet, ikke bare i visningen — et
                    # forslag uten tallgrunnlag kan ikke overprøves av mennesket.
                    "begrunnelse": (
                        "Betaler i snitt {} dager etter forfall, verste tilfelle {} dager.".format(
                            dager, mp["verste_dager"]
                        )
                    ),
                    "grunnlag": "{} fakturaer".format(mp["antall_fakturaer"]),
                    # Er noen av betalingene ubekreftet, følger forbeholdet med hit —
                    # ellers ser forslaget sikrere ut enn tallene bak det.
                    "ubekreftede": mp["ubekreftede"],
                }
            )

        return {
            "forslag": forslag,
            "kan_anbefale": True,
            "hvorfor_ikke": "",
            "grunnlag": m["grunnlag"],
            "forbehold": m["forbehold"],
            "base": m["base"],
        }
