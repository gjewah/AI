# -*- coding: utf-8 -*-
#
# Kommunikasjon – paraply-flatens data-lag (V01, 17.07.2026).
#
# Gjermund-beslutning: «Kommunikasjon» er ÉN flate som samler ALL kommunikasjon.
# E-post er ÉN kanal inne i den — ikke en egen flate, ikke i hovedmenyen.
#
# KANAL-REGISTER: hver kanal-modul (fiq_gui_epost, senere fiq_gui_whatsapp/_teams)
# melder seg inn ved å arve denne modellen og utvide _kanaler(). Paraplyen kjenner
# ingen kanal direkte → nye kanaler krever INGEN endring her.
#
# 000-KANON: scope hentes fra SESJONEN via KR-kjernens felles hjelper
# (fiq.gui.control.config.har_000_rettighet) — ALDRI fra klienten. Fail-closed.

from odoo import api, models
# Import-stien er verifisert mot Odoo 19s egen kilde (ir_actions.py:23), ikke antatt:
# `from odoo.tools.safe_eval import safe_eval`. Den ligger IKKE i `odoo.tools`-roten.
from odoo.tools.safe_eval import safe_eval


class FiqKommunikasjonData(models.AbstractModel):
    _name = "fiq.kommunikasjon.data"
    _description = "Kommunikasjon – paraply-flatens data-lag"

    # ---- Kanal-register -------------------------------------------------------------
    def _kanaler(self):
        """Registrerte kanaler. Kanal-moduler UTVIDER denne (super() + append).

        Hver kanal: {
          "kode": teknisk kode,       "navn": vist navn (norsk),
          "ikon": emoji/kort merke,   "farge": fargekart-navn,
          "action": xmlid til kanalens flate (valgfri),
          "antall": ulest/aktiv-teller (valgfri, int),
          "sekvens": rekkefølge i kanal-filteret,
        }
        Paraplyen kjenner INGEN kanal direkte — den spør bare registeret.
        """
        return []

    @api.model
    def get_kanaler(self):
        """Kanal-filteret: «Alle» + de kanalene som faktisk er installert.
        Rekkefølge = sekvens. Tomt register → kun «Alle» (flaten er da et skall)."""
        kanaler = sorted(self._kanaler(), key=lambda k: k.get("sekvens", 50))
        total = sum(int(k.get("antall") or 0) for k in kanaler)
        alle = {"kode": "alle", "navn": "Alle", "ikon": "✳", "farge": "accent",
                "antall": total, "sekvens": 0}
        return [alle] + kanaler

    # ---- Scope (000-kanon) ----------------------------------------------------------
    def _har_000_rettighet(self):
        """Kryss-firma-innsyn = RETTIGHET, ikke visnings-innstilling.
        Bruker KR-kjernens felles hjelper (Økt 02, KR v6.76). Fail-closed hvis den mangler."""
        KR = "fiq.gui.control.config"
        if KR in self.env and hasattr(self.env[KR], "har_000_rettighet"):
            try:
                return bool(self.env[KR].har_000_rettighet())
            except Exception:
                return False
        return False

    def _tillatte_firmaer(self):
        """Firmaene brukeren lovlig kan se. Delegerer til KR-kjernens felles
        `tillatte_firmaer()` (Økt 02) — regelen finnes ÉTT sted, kopieres aldri.
        Fail-closed til eget firma hvis kjernen mangler."""
        KR = "fiq.gui.control.config"
        if KR in self.env and hasattr(self.env[KR], "tillatte_firmaer"):
            try:
                return self.env[KR].tillatte_firmaer() or self.env.company.ids
            except Exception:
                return self.env.company.ids
        return self.env.company.ids

    @api.model
    def get_my_config(self):
        """Oppstarts-config til paraply-flaten. Firmavelgeren er et FILTER, ikke en
        tilgangsmekanisme — den viser kun firmaer brukeren FAKTISK har rett til."""
        kryss = self._har_000_rettighet()
        tillatte = self._tillatte_firmaer()
        firms = [{"id": c.id, "navn": c.name,
                  "kode": c.code if "code" in c._fields else ""}
                 for c in self.env["res.company"].browse(tillatte).exists()]
        if kryss and len(firms) > 1:
            firms = [{"id": False, "navn": "Alle", "kode": "∗"}] + firms
        return {
            "firms": firms,
            "current_firm": self.env.company.id,
            "kryss_firma": kryss,
            "user": self.env.user.name,
            "kanaler": self.get_kanaler(),
        }

    # ---- Oversikten (forsiden): fargebokser + Til stede ------------------------------
    # ORIGINALEN (V00.04-designet), ikke hjulene fra Forslag A. Gjermund 18.07.2026:
    # «vi ble enige om å kutte hjulene og ta den originale som var før den».
    # Paraplyen EIER oversikten; kanalene leverer boksene inn via registeret.

    def _bokser(self):
        """Boks-data. Kanal-moduler UTVIDER denne (super() + append), som _kanaler().
        Hver boks: {kode, navn, count, farge, gruppe} — gruppe = basis|tverrgaende|omraade."""
        return []

    @api.model
    def get_oversikt(self, firm=False):
        """Forsiden: fargeboksene (basis · tverrgående · områder 0–8) + «Til stede».
        Tomme bokser merkes så flaten kan skjule dem til de får innhold."""
        bokser = self._bokser()
        for b in bokser:
            b["tom"] = not int(b.get("count") or 0)
        grupper = {"basis": [], "tverrgaende": [], "omraade": []}
        for b in bokser:
            grupper.setdefault(b.get("gruppe", "omraade"), []).append(b)
        return {"grupper": grupper, "presence": self.get_presence(),
                "kr_meny": self.get_kr_meny()}

    @api.model
    def get_kr_meny(self):
        """Hovedmenyen fra Kontrollrommet — skal stå fast til venstre, I TILLEGG til
        Kommunikasjons eget mappetre (Gjermund 19.07.2026: «i tillegg»).

        Vi leser KR-kjernens EGEN `get_fiq_flater()` — samme kilde Kontrollrommet selv
        bruker. Da kan menyen aldri drifte fra KRs: melder en ny modul seg inn der, dukker
        den opp her også, uten at denne fila endres.

        Fail-closed til tom liste: mangler kjernen, viser vi ingen KR-meny framfor å gjette
        på en. En feil meny er verre enn ingen.
        """
        KR = "fiq.gui.control.config"
        if KR in self.env and hasattr(self.env[KR], "get_fiq_flater"):
            try:
                return self.env[KR].get_fiq_flater() or []
            except Exception:
                return []
        return []

    @api.model
    def aapne_boks(self, kode, kanal="epost"):
        """Klikk på en fargeboks → åpne kanalens flate FILTRERT på den boksen.

        Gjermund 18.07.2026: «viktig at riktig mappe åpnes når jeg trykker på en av boksene
        og da åpnes f.eks. "Haster" alle meldinger som haster. Klikker jeg deretter på en
        e-post skal epost åpne med å vise de som haster.»

        Boksen bærer selv hvilken kanal den kom fra (`_bokser()` setter "kanal"), så
        paraplyen slipper å vite noe om e-post spesielt. Filteret sendes i handlingens
        kontekst — kanalflaten leser det ved oppstart.
        """
        for k in self._kanaler():
            if k.get("kode") != kanal or not k.get("action"):
                continue
            try:
                act = self.env["ir.actions.actions"]._for_xml_id(k["action"])
            except Exception:
                return False
            # 🔴 KRASJET FLATEN (Gjermund 19.07: RPC_ERROR ved klikk på en samleboks).
            # `context` er et **Char-felt** på handlingen — verifisert i Odoo 19s kilde:
            # `ir_actions.py:312  context = fields.Char(...)`. Det kommer altså ut som
            # TEKST, ikke dict. `dict("{'a': 1}")` får Python til å tolke hvert TEGN som
            # et nøkkelpar → «dictionary update sequence element #0 has length 1».
            # Odoo løser det selv med `safe_eval` (samme fil, linje 351) — vi gjør likt.
            # `isinstance`-sjekken gjør det robust begge veier hvis Odoo en dag gir dict.
            # 🛑 Aldri `eval()` her: konteksten kommer fra databasen.
            raa = act.get("context") or {}
            ctx = dict(safe_eval(raa)) if isinstance(raa, str) else dict(raa)
            ctx["fiq_boks"] = kode                  # kanalflaten åpner filtrert på denne
            act["context"] = ctx
            return act
        return False

    @api.model
    def get_presence(self):
        """«Til stede» — delegerer til KR-kjernen så det betyr det SAMME overalt.
        Fail-closed til tom liste hvis kjernen mangler (aldri gjett hvem som er til stede)."""
        KR = "fiq.gui.control.config"
        if KR in self.env and hasattr(self.env[KR], "get_presence"):
            try:
                return self.env[KR].get_presence()
            except Exception:
                return []
        return []

    @api.model
    def get_kr_kobling(self):
        """Til KR-kjernen: hvor «Kommunikasjon» i Kontrollrommet skal peke.

        KR peker i dag til `fiq_gui_epost.action_fiq_gui_epost` (kanalen) — den bør peke
        hit (paraplyen), så brukeren lander på Kommunikasjon-forsiden og velger kanal der.
        Eksponert som metode så KR kan lese den uten å hardkode xmlid-en vår.
        """
        return {
            "kode": "gui_comm",
            "navn": "Kommunikasjon",
            "action": "fiq_gui_comm.action_fiq_gui_comm",
            "erstatter": "fiq_gui_epost.action_fiq_gui_epost",
        }

    @api.model
    def aapne_kanal(self, kode):
        """Åpne en kanals egen flate. Returnerer handling, eller False hvis kanalen
        ikke har en egen flate (da vises den inne i paraplyen)."""
        for k in self._kanaler():
            if k.get("kode") == kode and k.get("action"):
                return self.env["ir.actions.actions"]._for_xml_id(k["action"])
        return False
