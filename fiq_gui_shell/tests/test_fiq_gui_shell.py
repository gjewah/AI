#
# Tester for FIQ GUI-skallet.
#
# 🔴 HVORFOR DENNE FILA FINNES (22.07.2026):
# Skallet hadde NULL tester — og SJU flater har `fiq_gui_shell` i `depends`.
# Natt til 22.07 felte en kontrakt i skallet HELE grensesnittet: `label`-skjemaet krevde
# String, mens kommentaren tre linjer under sa «tåler tekst ELLER {en_US, nb_NO}».
# Relasjoner fulgte kommentaren i god tro → blank skjerm for alle.
#
# Det ble oppdaget PÅ Staging, av Gjermund, midt på natten. En test her ville fanget det.
#
# 🛑 MERK GRENSEN: disse testene sjekker KONTRAKTEN og at filene henger sammen.
# De kan IKKE erstatte port 7 (nettleser). Registry-kollisjon, OWL-kompileringsfeil og
# `if` i inline `t-on-*` lever kun i nettleseren, med HELT REN serverlogg. Ingen
# server-test ser dem — heller ikke denne.

import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import file_path


# post_install: testene leser modulfiler og registeret. `at_install` kjører midt i
# installasjonen, der registeret kun har modulens egne depends.
@tagged("-at_install", "post_install")
class TestFiqGuiShell(TransactionCase):
    def _les(self, sti):
        with open(file_path(sti), "r", encoding="utf-8") as f:
            return f.read()

    # ── KONTRAKTEN SOM FELTE GRENSESNITTET ────────────────────────────────────────
    def test_label_godtar_bade_tekst_og_sprakoppslag(self):
        """`label` i flate-registeret MÅ godta tekst OG {en_US, nb_NO}.

        Dette er selve feilen fra natt til 22.07: skjemaet krevde `{type: String}`,
        så en flate som sendte språk-objekt ble avvist — og avvisningen kastet i
        FLATENS modul under lasting, som tok ned hele modulgrafen.
        """
        js = self._les("fiq_gui_shell/static/src/shell.js")
        self.assertIn("addValidation", js, "flate-registeret mangler validering")
        # Skjemaet skal IKKE låse label til String alene.
        self.assertNotRegex(
            js,
            r"label:\s*\{\s*type:\s*String\s*\}",
            "label er låst til String — en flate med {en_US, nb_NO} vil felle "
            "HELE grensesnittet. Det skjedde 22.07 (Relasjoner).",
        )
        # Den skal ha en validator som slipper gjennom begge former.
        self.assertRegex(
            js,
            r"label:\s*\{\s*validate:",
            "label mangler validator som godtar både tekst og språk-oppslag",
        )

    def test_label_oversettes_for_visning(self):
        """Et språk-objekt MÅ oversettes før det vises.

        Malen skriver `label` rått til skjermen (shell.xml). Uten oversettelse ville
        menyen vist «[object Object]» — koden ville kjørt fint, resultatet vært feil.
        """
        js = self._les("fiq_gui_shell/static/src/shell.js")
        self.assertRegex(js, r"_tekst\s*\(", "skallet mangler oversettelse av label før visning")
        self.assertIn("nb_NO", js, "oversettelsen må kjenne nb_NO — norsk før engelsk (kanon 19.07)")

    # ── VAKTEN SOM SELV VAR EN ENKELTFEILKILDE ────────────────────────────────────
    def test_meny_er_valgfri(self):
        """`meny` MÅ være valgfri.

        Flater uten egen undermeny skal ikke merke at kontrakten finnes. Var den
        påkrevd, ville hver eksisterende flate blitt avvist ved neste lasting.
        """
        js = self._les("fiq_gui_shell/static/src/shell.js")
        self.assertRegex(
            js,
            r"meny:\s*\{[^}]*optional:\s*true",
            "meny må være optional — ellers avvises alle flater som ikke har undermeny",
        )

    # ── FELLER SOM HAR KOSTET TID FØR ─────────────────────────────────────────────
    def test_ingen_if_setning_i_inline_handler(self):
        """🛑 OWL kompilerer IKKE `if` inne i `t-on-*`.

        Uttrykkskompilatoren leser `if` som en kontekstvariabel og lager ugyldig JS →
        HELE malen dør for alle brukere. Skjedde i Kontrollrommet v6.41.
        Verken XML-validering eller `node --check` fanger den. Bruk ternær i stedet.
        """
        xml = self._les("fiq_gui_shell/static/src/shell.xml")
        for treff in re.findall(r't-on-\w+="([^"]*)"', xml):
            self.assertNotRegex(
                treff,
                r"\bif\s*\(",
                "`if (` i en inline t-on-handler dreper hele malen — bruk ternær",
            )

    def test_ingen_dobbel_bindestrek_i_xml_kommentar(self):
        """🛑 To bindestreker inne i en XML-kommentar gjør HELE fila ugyldig.

        Meldt av salgssporet 21.07: de skrev navnet på et kommandolinjeflagg i en
        kommentar og drepte malfila. Symptomet er blank skjerm med ren serverlogg;
        årsaken ser helt harmløs ut i en diff.
        """
        xml = self._les("fiq_gui_shell/static/src/shell.xml")
        for kommentar in re.findall(r"<!--(.*?)-->", xml, re.DOTALL):
            self.assertNotIn(
                "--",
                kommentar,
                "to bindestreker i en XML-kommentar gjør hele malfila ugyldig",
            )

    def test_gui_build_ikke_relevant_for_skallet(self):
        """Skallet har ingen GUI_BUILD-konstant — og skal ikke ha det.

        Kontrollrommet har én (versjonsvakt mot «ny versjon installert»-banneret).
        Får skallet sin egen, får vi to versjonssannheter som kan drifte fra hverandre.
        Denne testen holder den grensen.
        """
        js = self._les("fiq_gui_shell/static/src/shell.js")
        self.assertNotIn(
            "GUI_BUILD",
            js,
            "skallet skal ikke ha egen versjonskonstant — Kontrollrommet eier den",
        )
