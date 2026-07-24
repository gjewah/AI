from odoo import fields, models

from .res_company import AGA_SONER


class HrVersion(models.Model):
    # hr.version er Odoo 19s KONTRAKTSMODELL. Modulen hr_contract finnes ikke
    # lenger — den er slaatt sammen inn i hr. Loennsarter refererer derfor til
    # `version.<felt>`, ALDRI `contract.<felt>`; Odoo 18-eksempler er utdaterte.
    _inherit = "hr.version"

    # UNNTAKET FOR AMBULERENDE VIRKSOMHET (Skatteetaten, retningslinjer for valg
    # av avgiftssone): «Dersom arbeidstakeren utfoerer hoveddelen av sitt arbeid i
    # en annen sone enn i den sonen virksomheten er registrert, og
    # enhetsregisterreglene paa grunn av virksomhetens karakter ikke tillater
    # registrering av underenhet i sonen hvor arbeidet utfoeres, skal satsen i den
    # sonen hvor arbeidet utfoeres benyttes.»
    #
    # Gjelder typisk transport, bygg og anlegg — bransjer som ikke kan registrere
    # underenhet paa hvert oppdragssted.
    # 🛑 Utleie av arbeidskraft er IKKE omfattet av unntaket. For utleiefirmaer
    # gjelder hovedregelen: virksomhetens lokalisering avgjoer sonen.
    #
    # Feltet er et UNNTAK og skal staa tomt i normaltilfellet. Er det tomt,
    # brukes selskapets sone.
    fiq_aga_sone_override = fields.Selection(
        AGA_SONER,
        string="Sone — ambulerende arbeid",
        help="Fylles KUN ut naar arbeidstakeren utfoerer hoveddelen av arbeidet i "
        "en annen sone enn virksomheten er registrert i, OG virksomhetens "
        "karakter ikke tillater registrering av underenhet der arbeidet "
        "utfoeres (typisk transport, bygg og anlegg). "
        "Gjelder IKKE utleie av arbeidskraft. "
        "Staar feltet tomt, brukes selskapets sone.",
    )

    # FERIEPENGER — ferieuker avgjoer satsen (ferieloven § 10).
    # Lovens minstekrav er 4 uker + 1 dag (10,2 %). Fem uker er AVTALT, ikke
    # lovbestemt — derfor et felt og ikke en antakelse.
    fiq_ferie_fem_uker = fields.Boolean(
        string="Fem ukers ferie avtalt",
        help="Gir 12 % feriepenger i stedet for lovens 10,2 %. Foelger av "
        "tariffavtale eller individuell avtale, ikke av ferieloven.",
    )


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # Speiling til ansattkortet, samme moenster som l10n_lt_hr_payroll bruker.
    # groups= begrenser hvem som ser feltet: sonen henger sammen med hvor en
    # person faktisk arbeider, og er ikke allmenn ansattinformasjon.
    fiq_aga_sone_override = fields.Selection(
        readonly=False,
        related="version_id.fiq_aga_sone_override",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )

    fiq_ferie_fem_uker = fields.Boolean(
        readonly=False,
        related="version_id.fiq_ferie_fem_uker",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
