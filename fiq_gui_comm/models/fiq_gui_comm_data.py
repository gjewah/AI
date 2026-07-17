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

    @api.model
    def get_my_config(self):
        """Oppstarts-config til paraply-flaten. Firmavelgeren er et FILTER, ikke en
        tilgangsmekanisme — den viser kun firmaer brukeren FAKTISK har rett til."""
        kryss = self._har_000_rettighet()
        tillatte = (self.env.user.company_ids.ids or self.env.company.ids) \
            if kryss else self.env.company.ids
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
