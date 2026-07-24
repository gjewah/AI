#
# Tester for Kommunikasjon-paraplyen.
#
# Bakgrunn: modulen hadde NULL tester fram til 22.07.2026 — `--test-enable` kjørte
# derfor ingenting for den, og «grønn Staging» beviste bare at koden lastet.
# Testene under dekker de feilene som FAKTISK har truffet denne modulen, ikke
# tenkte tilfeller:
#   · `context` er et Char-felt, ikke dict  → RPC_ERROR ved hvert klikk på en boks
#   · `label` må være ren tekst             → objekt felte HELE grensesnittet (22.07)
#   · scope skal aldri komme fra klienten   → 000-kanon, fail-closed
#
# post_install: andre installerte moduler legger NOT NULL-kolonner på project.project
# og res.partner. Under at_install har registryet kun DENNE modulens depends, feltene
# er ukjente, defaults settes aldri i Python → NotNullViolation. post_install gir fullt
# registry og speiler hvordan koden faktisk kjører.

import json

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("-at_install", "post_install")
class TestKommunikasjon(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Data = self.env["fiq.kommunikasjon.data"]

    # ---- Kanal-registeret ---------------------------------------------------------

    def test_kanal_register_har_alltid_alle(self):
        """«Alle» skal alltid finnes, også når ingen kanal er installert."""
        kanaler = self.Data.get_kanaler()
        self.assertTrue(kanaler, "kanal-lista skal aldri være tom")
        self.assertEqual(kanaler[0]["kode"], "alle", "«Alle» skal ligge først")

    def test_alle_summerer_kanalenes_tall(self):
        """Totalen på «Alle» er summen av kanalene — ikke et eget oppslag."""
        kanaler = self.Data.get_kanaler()
        alle = kanaler[0]
        rest = sum(int(k.get("antall") or 0) for k in kanaler[1:])
        self.assertEqual(int(alle.get("antall") or 0), rest)

    # ---- Oversikten (forsiden) ----------------------------------------------------

    def test_oversikt_har_forventet_form(self):
        """Forsiden skal alltid få de tre gruppene, også når de er tomme —
        ellers må front-enden gjette på om nøkkelen mangler eller er tom."""
        o = self.Data.get_oversikt()
        self.assertIn("grupper", o)
        for g in ("basis", "tverrgaende", "omraade"):
            self.assertIn(g, o["grupper"])
            self.assertIsInstance(o["grupper"][g], list)
        self.assertIn("kr_meny", o)
        self.assertIsInstance(o["presence"], list)

    def test_tomme_bokser_er_merket(self):
        """Bokser uten innhold merkes `tom` så flaten kan skjule dem
        (Gjermund: «vær dynamisk, ikke vis bokser som er tomme»)."""
        o = self.Data.get_oversikt()
        for gruppe in o["grupper"].values():
            for b in gruppe:
                self.assertIn("tom", b)
                self.assertEqual(bool(b["tom"]), not int(b.get("count") or 0))

    # ---- 000-kanon: scope fra sesjonen, aldri fra klienten -------------------------

    def test_config_gir_kun_lovlige_firmaer(self):
        """Firmavelgeren er et FILTER, ikke en tilgangsmekanisme. Uten
        000-rettighet skal kun eget firma være med."""
        cfg = self.Data.get_my_config()
        self.assertIn("firms", cfg)
        if not cfg.get("kryss_firma"):
            ids = [f["id"] for f in cfg["firms"] if f["id"]]
            self.assertEqual(ids, self.env.company.ids)

    def test_000_er_fail_closed(self):
        """Mangler KR-kjernen, skal svaret være NEI — aldri «antatt ja»."""
        self.assertIsInstance(self.Data._har_000_rettighet(), bool)

    # ---- Krasjet 19.07: context er Char, ikke dict ---------------------------------

    def test_aapne_boks_taaler_context_som_tekst(self):
        """REGRESJON: `_for_xml_id()` gir `context` som STRENG (Odoo 19
        `ir_actions.py:312` → fields.Char). `dict(str)` ga
        «dictionary update sequence element #0 has length 1» ved HVERT klikk
        på en samleboks. Skal aldri kaste igjen."""
        try:
            act = self.Data.aapne_boks("uleste", kanal="epost")
        except Exception as e:  # pragma: no cover
            self.fail(f"aapne_boks kastet: {e}")
        if act:  # kanalen er installert
            self.assertIsInstance(
                act.get("context"),
                dict,
                "context skal være parset til dict før den sendes videre",
            )
            self.assertEqual(act["context"].get("fiq_boks"), "uleste")

    def test_aapne_boks_ukjent_kanal_gir_false(self):
        """Ukjent kanal skal gi False, ikke krasj."""
        self.assertFalse(self.Data.aapne_boks("uleste", kanal="finnes_ikke"))

    # ---- Feilklasse 10: label MÅ være ren tekst ------------------------------------

    def test_flate_registrering_har_ren_tekst_label(self):
        """REGRESJON: et objekt {en_US, nb_NO} i `label` felte HELE grensesnittet
        22.07 («Invalid object: 'label' is not a string»). Skjemaet i shell.js
        låser feltet til String. Vi leser vår egen registrering fra kilden."""
        import os
        import re

        sti = os.path.join(os.path.dirname(__file__), "..", "static", "src", "comm.js")
        with open(os.path.abspath(sti), encoding="utf-8") as f:
            kilde = f.read()
        self.assertIn(
            'registry.category("fiq_gui_flates")',
            kilde,
            "flaten må registrere seg i skallet",
        )

        # 🔑 NØKKELEN SKAL VÆRE «komm» (avklart 23.07). Menyen kaller «kommunikasjon»,
        # men KR oversetter selv i `_slotKomponent()` via `NOKKEL_ALIAS`
        # (`control_room.js:1811`). Døper flate-eierne om hver sin nøkkel, får vi fem
        # uavhengige fikser på et delt register. «komm» matcher dessuten
        # `fiq_gui_comm_flate.xml` og modellen `fiq.gui.komm.data` — bytter vi her,
        # brytes de to.
        nokler = re.findall(r'fiq_gui_flates"\)\.add\("([a-z_]+)"', kilde)
        self.assertIn(
            "komm",
            nokler,
            "nøkkelen må være «komm» — KR oversetter menyens navn via NOKKEL_ALIAS",
        )

        # `label` MÅ være streng-literal uansett hvor i fila den står. Vi sjekker ALLE
        # forekomster, ikke bare den etter registreringen — feilklasse 10 er at et
        # objekt {en_US, nb_NO} feller HELE grensesnittet.
        labels = re.findall(r"label:\s*(.)", kilde)
        self.assertTrue(labels, "fant ingen label å kontrollere")
        for tegn in labels:
            self.assertEqual(tegn, '"', "label må være streng-literal, ikke objekt")

    def test_kr_menyoppforing_er_gyldig_json(self):
        """Malformert JSON i selvregistreringen droppes STILLE av
        `get_fiq_flater()` → flaten blir usynlig uten feilmelding."""
        import os

        sti = os.path.join(
            os.path.dirname(__file__), "..", "data", "fiq_gui_comm_flate.xml"
        )
        with open(os.path.abspath(sti), encoding="utf-8") as f:
            xml = f.read()
        verdi = xml.split('<field name="value">', 1)[1].split("</field>", 1)[0]
        spec = json.loads(verdi)  # kaster hvis malformert
        self.assertIsInstance(spec.get("label"), str)
        self.assertTrue(spec.get("xmlid"))
        self.assertTrue(
            self.env.ref(spec["xmlid"], raise_if_not_found=False),
            "xmlid i selvregistreringen må finnes i basen",
        )

    # ---- Samleboks til KR-forsiden ------------------------------------------------

    def test_kr_boks_har_kontraktens_felt(self):
        """Kontrakten fra AI KR: haster · i_dag · totalt · linjer."""
        boks = self.env["fiq.gui.komm.data"].get_kr_boks()
        for felt in ("haster", "i_dag", "totalt", "linjer"):
            self.assertIn(felt, boks)
        self.assertIsInstance(boks["linjer"], list)
        self.assertLessEqual(len(boks["linjer"]), 5, "topp 5, ikke en hel liste")
