# -*- coding: utf-8 -*-
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
        self.company_id.sudo().write({
            "fiq_aga_fribelop_brukt": brukt + min(besparelse, gjenstaaende),
            "fiq_aga_fribelop_aar": aar,
        })

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
        return self.version_id.fiq_aga_sone_override or self.company_id.fiq_aga_sone or None

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
                "Sone for arbeidsgiveravgift mangler for %s. Sett sonen paa "
                "selskapet, eller paa ansattes kontrakt ved ambulerende arbeid."
                % (self.company_id.display_name,)
            )

        satser = self._rule_parameter("no_aga_sonesatser")
        if sone not in satser:
            raise ValueError(
                "Ukjent sone %r for arbeidsgiveravgift. Kjente soner: %s"
                % (sone, ", ".join(sorted(satser)))
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
            self.line_ids.filtered(lambda l: l.category_id.code == "BASIC").mapped("total")
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
            fribelop, self._fiq_aga_aar(),
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
            grunnlag_redusert * sats / 100.0
            + grunnlag_full * full_sats / 100.0
        ), "delvis"
