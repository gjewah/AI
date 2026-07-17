# -*- coding: utf-8 -*-
#
# E-post melder seg inn som KANAL i Kommunikasjon-paraplyen (fiq_gui_comm).
#
# Gjermund-beslutning 17.07.2026: «Kommunikasjon» er flaten; e-post er ÉN kanal inne i den
# og vises IKKE i hovedmenyen. Denne modulen beholder sitt tekniske navn (fiq_gui_epost) —
# ingen omdøping av installert modul («modul forsvinner mens installert»-fella).
#
# Paraplyen kjenner ingen kanal direkte; kanalen melder seg selv inn her.
# Er ikke fiq_gui_comm installert, gjør denne filen ingenting (arvet modell finnes ikke).

from odoo import models


class FiqKommunikasjonDataEpost(models.AbstractModel):
    _inherit = "fiq.kommunikasjon.data"

    def _kanaler(self):
        """Meld E-post inn i kanal-filteret, med ekte ulest-tall."""
        kanaler = super()._kanaler()
        ulest = 0
        try:
            data = self.env["fiq.meldingssenter.data"].get_meldingssenter_data()
            ulest = int(data.get("uleste") or 0)
        except Exception:
            ulest = 0                       # aldri la en teller velte flaten
        kanaler.append({
            "kode": "epost",
            "navn": "E-post",
            "ikon": "✉",
            "farge": "blaa",
            "action": "fiq_gui_epost.action_fiq_gui_epost",
            "antall": ulest,
            "sekvens": 10,
        })
        return kanaler
