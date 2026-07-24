from odoo import fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def action_payslip_done(self):
        """Bokfoerer loennsslippen — OG bruker av fribeloepet.

        🔑 Akkumuleringen skjer HER, ikke i `fiq_aga_belop()`. Beregningen
        leser hvor mye som er brukt; bare bokfoeringen SKRIVER. Ellers ville
        en forhaandsvisning eller en cashflow-framskrivning spist av
        fribeloepet uten at noen faktisk hadde kjoert loenn.

        Fribeloepet gjelder PER FORETAK PER AAR — derfor ligger telleren paa
        selskapet, ikke paa slippen.
        """
        res = super().action_payslip_done()
        for slip in self:
            slip._fiq_bruk_av_fribelop()
        return res

    def _fiq_bruk_av_fribelop(self):
        """Oeker selskapets forbrukte fribeloep med denne slippens besparelse."""
        self.ensure_one()
        if not self.company_id.fiq_aga_sone:
            # Ingen sone -> ingen beregning. Bokfoeringen stoppes ikke av det;
            # avviket fanges av `status_forpliktelser()` mot 2.80 RGS.
            return

        try:
            sats = self.fiq_aga_sats()
        except ValueError:
            return

        full_sats = self._rule_parameter("no_aga_full_sats")
        if sats >= full_sats:
            return  # Sonen har ingen fribeloepsmekanikk.

        grunnlag = self.fiq_aga_grunnlag()
        if not grunnlag:
            return

        aar = self._fiq_aga_aar()
        fribelop = self._rule_parameter("no_aga_fribelop")
        gjenstaaende = self.company_id.fiq_aga_fribelop_gjenstaaende(fribelop, aar)
        brukt = fribelop - gjenstaaende  # 0 hvis aaret er nytt

        # Bare den DELEN av besparelsen som faktisk daekkes av fribeloepet
        # skal telle — resten er allerede betalt med full sats.
        besparelse = grunnlag * (full_sats - sats) / 100.0
        self.company_id.sudo().write(
            {
                "fiq_aga_fribelop_brukt": brukt + min(besparelse, gjenstaaende),
                "fiq_aga_fribelop_aar": aar,
            }
        )

    # ==================================================================
    # FERIEPENGER — ferieloven § 10
    # ==================================================================
    def fiq_feriepenger_sats(self, opptjeningsaar=None):
        """Feriepengesats i prosent for denne ansatte.

        🔴 SATSEN AVHENGER AV ALDER — og alder er personopplysning. Derfor
        beregnes den HER, i HR, og bare summen forlater modulen.

        Ferieloven § 10: 10,2 % ordinaert · 12 % ved fem ukers ferie ·
        + 2,3 prosentpoeng for arbeidstaker over 60 med ekstraferie.

        🛑 «Over 60» er ikke alder paa utbetalingsdagen: retten til ekstraferie
        gjelder fra og med det AARET arbeidstakeren FYLLER 60. Bruker vi alder
        i dag, faar en som fyller 60 i desember feil sats hele aaret.
        """
        self.ensure_one()
        if opptjeningsaar is None:
            opptjeningsaar = self._fiq_aga_aar()

        satser = self._rule_parameter("no_feriepenger_satser")
        fem_uker = self.version_id.fiq_ferie_fem_uker
        if self._fiq_fyller_60_eller_mer(opptjeningsaar):
            return satser["over_60_fem_uker" if fem_uker else "over_60"]
        return satser["fem_uker" if fem_uker else "ordinaer"]

    def _fiq_fyller_60_eller_mer(self, opptjeningsaar):
        """Om arbeidstakeren fyller 60 eller mer I LOEPET AV opptjeningsaaret.

        Returnerer False naar foedselsdato mangler — da brukes ordinaer sats.
        Det er det forsiktige valget: aa gjette paa hoeyere sats ville gitt en
        for stor avsetning, og aa gjette i det hele tatt er forbudt naar
        grunnlaget er juridisk bindende.
        """
        self.ensure_one()
        fodselsdato = self.employee_id.birthday
        if not fodselsdato:
            return False
        return (opptjeningsaar - fodselsdato.year) >= 60

    def fiq_feriepenger_avsetning(self, grunnlag=None, opptjeningsaar=None):
        """Feriepengeavsetning for denne loennsslippen, i kroner.

        Haandterer 6 G-taket: tillegget for over 60 gjelder KUN for grunnlag
        opp til seks ganger grunnbeloepet (ferieloven § 10). Over taket brukes
        ordinaer sats paa det overskytende.
        """
        self.ensure_one()
        if grunnlag is None:
            grunnlag = self.fiq_aga_grunnlag()
        if not grunnlag:
            return 0.0
        if opptjeningsaar is None:
            opptjeningsaar = self._fiq_aga_aar()

        sats = self.fiq_feriepenger_sats(opptjeningsaar)
        if not self._fiq_fyller_60_eller_mer(opptjeningsaar):
            return grunnlag * sats / 100.0

        # Over 60: forhoeyet sats kun opp til 6 G.
        tak = self._rule_parameter("no_feriepenger_6g")
        satser = self._rule_parameter("no_feriepenger_satser")
        ordinaer = satser[
            "fem_uker" if self.version_id.fiq_ferie_fem_uker else "ordinaer"
        ]

        if grunnlag <= tak:
            return grunnlag * sats / 100.0
        return tak * sats / 100.0 + (grunnlag - tak) * ordinaer / 100.0

    # ==================================================================
    # OTP — obligatorisk tjenestepensjon (OTP-loven § 4)
    # ==================================================================
    def fiq_otp_sats(self):
        """Selskapets OTP-sats, eller lovens minstekrav om ingen er satt."""
        self.ensure_one()
        return self.company_id.fiq_otp_sats or self._rule_parameter("no_otp_minstesats")

    def fiq_otp_omfattet(self):
        """Om denne ansatte skal ha pensjonsinnskudd.

        🔑 «PENSJON FRA FOERSTE KRONE OG DAG» (LOV-2021-12-22-164) fjernet
        20 %-stillingsgrensen og senket aldersgrensen fra 20 til 13 aar.
        **Alder er den eneste gjenvaerende terskelen.**

        🛑 Bygger man paa en eldre beskrivelse av OTP, faar deltidsansatte og
        unge INGEN pensjon — og foretaket bryter loven uten at noe feiler.

        Manglende foedselsdato → omfattet. Det forsiktige valget peker MOTSATT
        vei her enn for feriepenger: der ga forsiktighet lavere avsetning, her
        gir den hoeyere. **Aa utelate noen fra pensjonsordningen er verre enn
        aa avsette for mye.**
        """
        self.ensure_one()
        fodselsdato = self.employee_id.birthday
        if not fodselsdato:
            return True
        min_alder = self._rule_parameter("no_otp_min_alder")
        return (self._fiq_aga_aar() - fodselsdato.year) >= min_alder

    def fiq_otp_innskudd(self, grunnlag=None):
        """Pensjonsinnskudd for denne loennsslippen, i kroner.

        Innskuddet beregnes av loenn opp til 12 G (OTP-loven § 4); loenn over
        taket gir ingen pliktig innskudd.

        ⚠️ **BEGRENSNING:** taket gjelder AARLIG loenn. Denne metoden maaler
        slippens eget grunnlag mot 12 G, ikke akkumulert loenn hittil i aaret.
        For maanedskjoeringer under taket er det riktig; for en ansatt som
        passerer 12 G i loepet av aaret, blir innskuddet for hoeyt i
        maanedene etter passeringen. **Ikke bygget — meldt som aapent.**
        """
        self.ensure_one()
        if grunnlag is None:
            grunnlag = self.fiq_aga_grunnlag()
        if not grunnlag or not self.fiq_otp_omfattet():
            return 0.0
        tak = self._rule_parameter("no_otp_12g")
        return min(grunnlag, tak) * self.fiq_otp_sats() / 100.0

    def _fiq_aga_aar(self):
        """Aaret loennsslippen hoerer til — styrer hvilket fribeloep som gjelder."""
        self.ensure_one()
        return (self.date_to or fields.Date.context_today(self)).year

    def fiq_aga_sone(self):
        """Sonen som gjelder for denne loennsslippen.

        Rekkefoelgen er lovbestemt, ikke en preferanse:
        1. Ansattes override — unntaket for ambulerende virksomhet, der
           hoveddelen av arbeidet utfoeres i en annen sone og underenhet ikke
           kan registreres der.
        2. Selskapets sone — HOVEDREGELEN. Virksomhetens registrerte
           lokalisering avgjoer satsen.

        Returnerer None naar ingen sone er satt. Da skal det ikke gjettes:
        se `fiq_aga_sats`.
        """
        self.ensure_one()
        return (
            self.version_id.fiq_aga_sone_override
            or self.company_id.fiq_aga_sone
            or None
        )

    def fiq_aga_sats(self):
        """Satsen i prosent for denne loennsslippen, slaatt opp per dato.

        Satsen hentes fra rule-parameteren, ikke fra kode — den endres hvert
        statsbudsjett, og `hr.rule.parameter` velger riktig versjon ut fra
        `date_to`. Det er hele grunnen til at satsene ligger som data.

        🛑 Kaster ValueError hvis sone mangler eller er ukjent. Det er med
        vilje: arbeidsgiveravgift er juridisk bindende, og en manglende sone
        skal STOPPE loennskjoeringen — ikke gi 0 % eller en gjettet standardsats.
        En stille null her ville blitt en avviksmelding fra Skatteetaten.
        """
        self.ensure_one()
        sone = self.fiq_aga_sone()
        if not sone:
            raise ValueError(
                f"Sone for arbeidsgiveravgift mangler for {self.company_id.display_name}. Sett sonen paa "
                "selskapet, eller paa ansattes kontrakt ved ambulerende arbeid."
            )

        satser = self._rule_parameter("no_aga_sonesatser")
        if sone not in satser:
            raise ValueError(
                "Ukjent sone {!r} for arbeidsgiveravgift. Kjente soner: {}".format(
                    sone, ", ".join(sorted(satser))
                )
            )
        return satser[sone]

    def fiq_aga_grunnlag(self):
        """Avgiftsgrunnlaget: summen av loennsarter merket som avgiftspliktige.

        Grunnlaget er IKKE det samme som utbetalt loenn — naturalytelser er
        avgiftspliktige uten aa utbetales, og enkelte trekk reduserer ikke
        grunnlaget. Derfor summeres kategorien, ikke nettobeloepet.
        """
        self.ensure_one()
        return sum(
            self.line_ids.filtered(lambda l: l.category_id.code == "BASIC").mapped(
                "total"
            )
        )

    def fiq_aga_belop(self, grunnlag=None):
        """Arbeidsgiveravgift for denne loennsslippen, i kroner.

        `grunnlag` kan sendes inn for aa regne paa et annet beloep enn
        loennsslippens eget — brukes av tester og av framskrivninger. Utelates
        det, brukes slippens faktiske grunnlag.

        Haandterer fribeloepet for sone Ia og IVa: redusert sats gjelder bare
        saa lenge differansen mot full sats ligger innenfor fribeloepet. Naar
        fribeloepet er brukt opp, gjelder full sats for det overskytende.

        ⚠️ Fribeloepet gjelder PER FORETAK PER AAR. Denne metoden leser hvor mye
        som er brukt, men SKRIVER ikke — akkumuleringen maa skje naar
        loennsslippen bokfoeres, ikke naar beloepet regnes ut. Ellers ville en
        forhaandsvisning ha spist av fribeloepet.
        """
        self.ensure_one()
        if grunnlag is None:
            grunnlag = self.fiq_aga_grunnlag()
        if not grunnlag:
            return 0.0

        sats = self.fiq_aga_sats()
        full_sats = self._rule_parameter("no_aga_full_sats")

        # Soner uten fribeloepsmekanikk: ren sum x sats.
        if sats >= full_sats:
            return grunnlag * sats / 100.0

        return self._fribelop_belop(grunnlag, sats, full_sats)[0]

    def fiq_aga_fribelop_status(self, grunnlag=None):
        """Om fribeloepet paavirket denne beregningen — og hvordan.

        Returnerer None naar sonen ikke har fribeloepsmekanikk (alle unntatt
        Ia og IVa), ellers en av: 'innenfor' | 'delvis' | 'oppbrukt'.

        🔑 Finnes fordi 2.80 RGS spurte hvordan flaten skal forklare at
        AGA-beloepet HOPPER midt i aaret uten at loenna har endret seg. Svaret
        kan ikke utledes fra beloepets stoerrelse — det maa komme fra den som
        vet hvorfor. `periode` («Termin 3 2026») forklarer det ikke.
        """
        self.ensure_one()
        if grunnlag is None:
            grunnlag = self.fiq_aga_grunnlag()
        if not grunnlag:
            return None

        sats = self.fiq_aga_sats()
        full_sats = self._rule_parameter("no_aga_full_sats")
        if sats >= full_sats:
            return None
        return self._fribelop_belop(grunnlag, sats, full_sats)[1]

    def _fribelop_belop(self, grunnlag, sats, full_sats):
        """Beloep + status for soner med fribeloep. Returnerer (beloep, status)."""
        self.ensure_one()

        fribelop = self._rule_parameter("no_aga_fribelop")
        gjenstaaende = self.company_id.fiq_aga_fribelop_gjenstaaende(
            fribelop,
            self._fiq_aga_aar(),
        )

        # Besparelsen ved redusert sats — det er DEN som maales mot fribeloepet,
        # ikke avgiften selv.
        besparelse = grunnlag * (full_sats - sats) / 100.0

        if not gjenstaaende:
            # Fribeloepet var allerede brukt opp foer denne beregningen.
            return grunnlag * full_sats / 100.0, "oppbrukt"

        if besparelse <= gjenstaaende:
            return grunnlag * sats / 100.0, "innenfor"

        # Fribeloepet tar slutt MIDT i grunnlaget: den delen som daekkes av
        # fribeloepet faar redusert sats, resten full sats.
        grunnlag_redusert = gjenstaaende / ((full_sats - sats) / 100.0)
        grunnlag_full = grunnlag - grunnlag_redusert

        return (
            grunnlag_redusert * sats / 100.0 + grunnlag_full * full_sats / 100.0
        ), "delvis"
