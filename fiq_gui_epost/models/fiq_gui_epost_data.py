# -*- coding: utf-8 -*-
#
# Meldingssenter – data-lag (steg 1 av "native Meldingssenter").
# Leser EKTE tall fra Odoos meldingstabell (mail.message) i stedet for de
# oppdiktede tallene i V00.04-skissen. Kjører som den innloggede brukeren →
# record rules styrer synlighet (samme mønster som fiq_gui_control.get_kommunikasjon).
#
# Definisjoner (v1, dokumentert – "innboks/uleste/sendt"):
#   * sendt   = e-poster skrevet av en intern ansatt (utgående/logget av oss).
#   * innboks = ekte e-poster PÅ elementer (prosjekt/oppgave/kontakt) som IKKE er
#               internt forfattet (mottatt utenfra) = alle element-e-poster minus sendt.
#   * uleste  = meldinger som krever handling for den innloggede brukeren (Odoos
#               standard varsel-status, "needaction").
#
# Taksonomi-splitt (0–8) og paring kommer i senere steg (fiq_komm_match).

from datetime import timedelta

from odoo import api, fields, models

# Basisfilter: ekte kommunikasjon PÅ et element, ikke Discuss-kanaler.
# Speiler domenet i fiq_gui_control.get_kommunikasjon (verifisert mønster).
_ON_RECORD = [
    ("model", "!=", False),
    ("res_id", "!=", False),
    ("model", "not in", ["discuss.channel", "mail.channel"]),
]

_PERIOD_DAYS = {"dag": 1, "uke": 7, "maaned": 30}


class FiqMeldingssenterData(models.AbstractModel):
    _name = "fiq.meldingssenter.data"
    _description = "Meldingssenter – ekte tall fra mail.message"

    def _period_domain(self, period):
        """Legg på dato-avgrensning for dag/uke/maaned. 'alle' = ingen grense."""
        days = _PERIOD_DAYS.get(period)
        if days:
            return [("date", ">=", fields.Datetime.now() - timedelta(days=days))]
        return []

    @api.model
    def get_meldingssenter_data(self, firm=False, period="alle"):
        """Ekte basis-tall til Meldingssenter-flaten.

        Kjøres som brukeren → hver bruker teller kun det de har tilgang til.
        firm = firma-id (valgfri) → firma-scoping når firma-velgeren byttes i topplinja.
               Filter = mail.message.record_company_id (lagret felt = firmaet til elementet
               meldingen henger på) → bytt firma, tallene reberegnes umiddelbart.
        period = dag | uke | maaned | alle.
        Returns: {"innboks", "uleste", "sendt", "firm", "period"}
        """
        Msg = self.env["mail.message"]
        dom = self._period_domain(period)
        if firm:
            dom = dom + [("record_company_id", "=", int(firm))]

        # Alle ekte e-poster på et element (mottatt + sendt).
        epost_dom = _ON_RECORD + [("message_type", "=", "email")] + dom
        epost_totalt = Msg.search_count(epost_dom)

        # Sendt = e-poster forfattet av en intern ansatt (ikke share/portal-bruker).
        sendt = Msg.search_count(epost_dom + [("author_id.user_ids.share", "=", False)])

        # Innboks (mottatt) = alle element-e-poster minus de vi selv sendte.
        innboks = max(epost_totalt - sendt, 0)

        # Uleste = Odoos standard varsel-status for den innloggede brukeren.
        uleste = Msg.search_count([("needaction", "=", True)] + dom)

        return {
            "innboks": innboks,
            "uleste": uleste,
            "sendt": sendt,
            "firm": firm,
            "period": period,
        }
