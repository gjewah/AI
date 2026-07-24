"""AI-meldinger melder seg inn som KANAL i Kommunikasjon (Meldingssenteret).

Gjermund 19.07.2026: «AI-meldinger skal også være tilgjengelig som egen flate for alle
brukere i meldingssenteret slik at alle har oversikt over sin kommunikasjon og
forespørsler til AI»

MEKANISMEN FINNES ALLEREDE — vi bygger ingenting nytt her. `fiq.kommunikasjon.data._kanaler()`
i `fiq_gui_comm` er et register hver kanal-modul utvider med `super()` + append. Paraplyen
kjenner ingen kanal direkte, så en ny kanal krever INGEN endring i Kommunikasjon.
(Verifisert i `fiq_gui_comm/models/fiq_gui_comm_data.py:23-36`, ikke antatt.)

⚠️ Denne fila arver en modell fra en ANNEN modul (`fiq_gui_comm`). Derfor er `fiq_gui_comm`
lagt til i `depends` — uten det finnes ikke modellen ved lasting, og modulen krasjer.
Antallet er `krever_svar and not besvart` — det er de eneste meldingene som faktisk stopper
noe. Ro-budsjett: tallet skal bety «dette venter på deg», ikke «her er alt som finnes».
"""

from odoo import models


class FiqKommunikasjonDataAi(models.AbstractModel):
    _inherit = "fiq.kommunikasjon.data"

    def _kanaler(self):
        kanaler = super()._kanaler()
        try:
            # Savepoint: en SQL-feil her (tabell/kolonne mangler ved delvis oppgradering)
            # ville ellers avbryte transaksjonen og ta ned HELE Kommunikasjon-flaten,
            # ikke bare denne kanalen.
            with self.env.cr.savepoint():
                antall = self.env["fiq.ai.melding"].search_count(
                    self._ai_ubesvart_domene()
                )
        except Exception:
            # En kanal som feiler skal aldri ta ned hele Kommunikasjon-flaten.
            antall = 0
        kanaler.append(
            {
                "kode": "ai",
                "navn": "AI-meldinger",
                "ikon": "🤖",
                "farge": "lilla",  # 8.50 AI = lilla i det kanoniske fargekartet
                "action": "fiq_gui_ai_kr.action_fiq_ai_melding",
                "antall": antall,
                "sekvens": 20,
            }
        )
        return kanaler

    def _ai_ubesvart_domene(self):
        """Ubesvarte AI-meldinger brukeren HAR LOV til å se.

        🛑 Scope fra sesjonen: uten 000-rettighet ser man kun sine egne. Klienten kan
        ikke be seg til driftstrafikken ved å sende en parameter.
        """
        dom = [
            ("krever_svar", "=", True),
            ("besvart", "=", False),
            ("filtrert_bort", "=", False),
        ]
        Data = self.env.get("fiq.ai.melding.data")
        drift = bool(Data and Data._har_000())
        if not drift:
            dom.append(("bruker_id", "=", self.env.uid))
        return dom
