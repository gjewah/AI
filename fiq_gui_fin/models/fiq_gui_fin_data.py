# -*- coding: utf-8 -*-
"""Datakilde for AI GUI Finans (2.70) — samleboks til Kontrollrommet.

Rolle bak, flate foran: VISNINGEN av «0.00 2.70 AI Finans-Rådgiver».
Native-først — tallene EIES av Odoo (`account.move`). Ingen parallell logikk.

SKILLET MOT 2.80 (viktig — ellers blir de to boksene like):
  2.80 RGS  = LIKVIDITET — hva forfaller, hva er ubetalt, når blir det tight.
  2.70 FIN  = STYRING    — kredittrisiko: hvilke KUNDER skylder mye og lenge.
Gjermunds spec for 2.70 nevner det uttrykkelig: «kunder med faresignaler som
skylder mye penger». Det er kundenivå, ikke bilagsnivå — derfor grupperes det
per kunde her, mens 2.80 teller enkeltbilag.

🛑 «ALDRI gjett — regnskap er juridisk bindende»: kun bokførte tall (state=posted).
🛑 TENANT: firma via `with_company()` + `ir.rule` — aldri rå company_id fra klient.
🛑 KRYSS-TENANT: kun EGET firmas kunder. «Hva gjør andre» = bransjedata, aldri en
   annen FIQ-kundes tall. Den kilden er ikke avklart ennå → ikke bygget.
"""

from odoo import api, fields, models


class FiqGuiFinData(models.AbstractModel):
    """Leser kredittbildet. AbstractModel = ingen tabell, ingen lagrede tall."""

    _name = "fiq.gui.fin.data"
    _description = "FIQ Finans — styringsdata (lesing av account.move)"

    # Terskel for «skylder mye». Config-drevet senere (per firma, jf. Gjermunds krav
    # om utbyggbarhet); holdes som konstant til noen har bestemt beløpet.
    FARE_BELOP = 10000.0
    FARE_DAGER = 30

    @api.model
    def _kunde_domene(self, selv):
        """Ubetalte, bokførte KUNDEfakturaer for gjeldende firma."""
        return [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("payment_state", "not in", ("paid", "reversed")),
            ("company_id", "=", selv.env.company.id),
        ]

    @api.model
    def get_kr_boks(self, company_id=False):
        """Samleboks til KR-forsiden (kontrakt: fiq_gui_control_config.py:1335).

        For 2.70 er «saker» = KUNDER med faresignaler, ikke enkeltfakturaer:
          haster = kunder som skylder mye OG lenge (begge terskler)
          i_dag  = kunder med forfall i dag
          totalt = kunder med utestående i det hele tatt

        Kan tallet ikke regnes: ingen boks (None) — aldri 0. Se 2.80-modellen.
        """
        selv = self.with_company(company_id) if company_id else self
        i_dag = fields.Date.context_today(selv)
        grense = fields.Date.subtract(i_dag, days=selv.FARE_DAGER)
        Move = selv.env["account.move"]

        # Grupper per kunde: sum utestående + eldste forfall.
        grupper = Move._read_group(
            selv._kunde_domene(selv),
            groupby=["partner_id"],
            aggregates=["amount_residual:sum", "invoice_date_due:min"],
        )

        totalt = len(grupper)
        i_dag_ant = 0
        faresignal = []
        for partner, sum_rest, eldste in grupper:
            if eldste and eldste == i_dag:
                i_dag_ant += 1
            # Faresignal = skylder MYE og har ligget LENGE. Begge, ikke én av dem —
            # et stort ferskt beløp er ikke risiko, og en gammel bagatell er ikke det heller.
            if sum_rest >= selv.FARE_BELOP and eldste and eldste <= grense:
                faresignal.append((partner, sum_rest, eldste))

        faresignal.sort(key=lambda r: r[1], reverse=True)
        linjer = []
        for partner, sum_rest, eldste in faresignal[:5]:
            dager = (i_dag - eldste).days
            linjer.append({
                "tekst": "%s skylder %s kr — eldste %s dager" % (
                    partner.display_name, int(sum_rest), dager,
                ),
                "res_id": partner.id,
            })

        return {
            "haster": len(faresignal),
            "i_dag": i_dag_ant,
            "totalt": totalt,
            "linjer": linjer,
        }
