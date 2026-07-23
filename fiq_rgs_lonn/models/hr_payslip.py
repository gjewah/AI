# -*- coding: utf-8 -*-
from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

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

        fribelop = self._rule_parameter("no_aga_fribelop")
        brukt = self.company_id.fiq_aga_fribelop_brukt
        gjenstaaende = max(fribelop - brukt, 0.0)

        # Besparelsen ved redusert sats — det er DEN som maales mot fribeloepet,
        # ikke avgiften selv.
        besparelse = grunnlag * (full_sats - sats) / 100.0

        if besparelse <= gjenstaaende:
            return grunnlag * sats / 100.0

        # Fribeloepet tar slutt midt i grunnlaget: den delen som daekkes av
        # fribeloepet faar redusert sats, resten full sats.
        if full_sats > sats:
            grunnlag_redusert = gjenstaaende / ((full_sats - sats) / 100.0)
        else:
            grunnlag_redusert = 0.0
        grunnlag_full = grunnlag - grunnlag_redusert

        return (
            grunnlag_redusert * sats / 100.0
            + grunnlag_full * full_sats / 100.0
        )
