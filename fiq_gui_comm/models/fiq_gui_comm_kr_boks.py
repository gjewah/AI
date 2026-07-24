#
# Samleboks til KR-forsiden (kontrakten fra AI KR, 19.07.2026).
#
# KR-forsiden er en samling bokser — én per flate, med det som haster. Klikk → inn i rommet.
# For Kommunikasjon er det åpenbare innholdet: uleste + hva som venter svar.
#
# 🔑 HVORFOR EN EGEN MODELL, IKKE EN METODE PÅ `fiq.kommunikasjon.data`:
# AI KRs oppslag (`_finn_boks_leverandor`) leter KUN etter husets navnemønster
# `fiq.gui.<key>.data` — med `key` = selvregistreringsnøkkelen vår («komm»). Den prøver
# fire varianter, og INGEN av dem treffer `fiq.kommunikasjon.data`. Boksen ville derfor
# aldri blitt funnet, uansett hvor riktig den ellers var.
# Å døpe om `fiq.kommunikasjon.data` er utelukket: modellen er live på Staging, og
# omdøping av en installert modell er nettopp «modul forsvinner mens installert»-fella.
# Derfor dette tynne laget med KONTRAKTS-NAVNET, som delegerer til den ekte datakilden.
#
# Merk at AI KR selv gikk i en beslektet felle 19.07: nøkkelen bruker understrek
# («ai_kr»), modellnavn bruker punktum. Navnebroer som denne må være eksplisitte.

from odoo import api, models


class FiqGuiKommKrBoks(models.AbstractModel):
    _name = "fiq.gui.komm.data"
    _description = "Kommunikasjon – samleboks til KR-forsiden"

    @api.model
    def get_kr_boks(self, company_id=False):
        """Tall til KR-forsidens Kommunikasjon-boks.

        Kontrakt: {"haster": int, "i_dag": int, "totalt": int,
                   "linjer": [{"tekst": str, "res_id": int}, …]}

        Ro-budsjett (AI KRs krav): TALL, ikke varsler. Ingen popup, ingen alarm —
        forsiden skal svare på «hva nå?», ikke rope.
        """
        tom = {"haster": 0, "i_dag": 0, "totalt": 0, "linjer": []}
        DATA = "fiq.meldingssenter.data"
        if DATA not in self.env:
            return tom  # e-post-kanalen er ikke installert
        kilde = self.env[DATA]

        # Firmavalget fra KR kan kun SNEVRE INN — kildens egen `_firma_domene()` gjør
        # 000-sjekken selv. Vi sender bare valget videre; vi tolker aldri rettigheter her.
        try:
            data = kilde.get_boxes(firm=company_id or False, period="alle") or {}
        except Exception:
            return tom  # en feilende boks skal aldri velte forsiden

        def _tell(gruppe, kode):
            for b in data.get(gruppe) or []:
                if b.get("kode") == kode:
                    return int(b.get("count") or 0)
            return 0

        uleste = _tell("basis", "uleste")
        haster = _tell("tverrgaende", "haster")

        # «i_dag» = det som kom i dag. Vi teller på meldingsnivå fordi boks-tallene
        # ikke er datofiltrert — og vi vil ikke vise gårsdagens post som dagens.
        i_dag = 0
        linjer = []
        try:
            meldinger = (
                kilde.get_messages(
                    boks="uleste", firm=company_id or False, period="dag"
                )
                or []
            )
            i_dag = len(meldinger)
            for m in meldinger[:5]:  # topp 5, ikke en hel liste
                avsender = (m.get("fra") or "").strip()
                emne = (m.get("emne") or "").strip()
                linjer.append(
                    {
                        "tekst": (f"{avsender}: {emne}").strip(": ")[:90],
                        "res_id": m.get("id"),
                    }
                )
        except Exception:
            pass  # tallene står selv om linjene mangler

        return {"haster": haster, "i_dag": i_dag, "totalt": uleste, "linjer": linjer}
