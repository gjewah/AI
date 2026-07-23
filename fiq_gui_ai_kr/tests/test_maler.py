# -*- coding: utf-8 -*-
"""QWEB-MALENE — den ene feilklassen ingen annen test fanger.

🔴 BAKGRUNN, 23.07.2026: `styring.xml` hadde `and not q.kan_alltid`.
QWeb oversetter `and`/`or` til JavaScript, men IKKE `not` — den ble lest som et
VARIABELNAVN (`ctx['not']`), og hele malen ble ugyldig JS:
    «missing ) after argument list»
Gjermund fikk OwlError og **flaten var helt død i nettleseren**.

🔑 SAMTIDIG VAR 36 TESTER GRØNNE.
En QWeb-mal kompileres først NÅR NETTLESEREN LASTER DEN. Ingen server-test rører
malen, modulen installerer feilfritt, og loggen er 100 % ren. Det er port 7 i sin
reneste form — og nøyaktig samme klasse som `label`-kontrakten og Datetime-krasjet.

👉 DENNE FILA ER SVARET PÅ «hvordan hindrer vi at den kommer tilbake».
Den kan ikke bevise at flaten SER riktig ut — bare et menneske i en nettleser kan
det. Men den fanger uttrykk som gjør malen usyntaktisk før den når nettleseren.
"""

import os
import re

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMaler(TransactionCase):

    # Python-operatorer som IKKE finnes i JavaScript. QWeb oversetter `and`/`or`,
    # men lar disse stå — og da blir de lest som variabelnavn.
    # Ordgrense på begge sider, ellers treffer «not» inni «cannot», «notat» osv.
    FORBUDT = [
        (r"\bnot\s+", "not", "bruk ! i stedet"),
        (r"\bis\s+None\b", "is None", "bruk === undefined / === null"),
        (r"\bis\s+not\b", "is not", "bruk !== "),
        (r"\bTrue\b", "True", "bruk true (liten t)"),
        (r"\bFalse\b", "False", "bruk false (liten f)"),
        (r"\bNone\b", "None", "bruk null eller undefined"),
        (r"\belif\b", "elif", "QWeb bruker t-elif som attributt, ikke i uttrykk"),
    ]

    # Attributtene som inneholder JavaScript-uttrykk. `t-attf-*` er utelatt:
    # den bruker {{…}}-interpolasjon og har egne regler.
    #
    # 🔴 MØNSTERET MÅTTE RETTES FØR DET VIRKET (23.07): første utgave brukte
    # `["']([^"']*)["']` og stoppet på den FØRSTE apostrofen inne i uttrykket.
    # `t-att-disabled="k.valg === 'alltid' and not q.kan_alltid"` ga treffet
    # `k.valg === ` — og `not` ble aldri sett. Testen var GRØNN på den ekte feilen
    # den ble skrevet for å fange.
    # 🔑 Samme klasse som feilen den vokter: noe som ser ut til å måle, og ikke gjør det.
    # Derfor: bind til dobbeltfnutt, som er det XML faktisk bruker for attributter.
    UTTRYKKS_ATTR = re.compile(
        r'''t-(?:att-[\w-]+|if|elif|else|esc|out|foreach|key|value|on-\w+)\s*=\s*"([^"]*)"''',
        re.S,
    )

    def _mal_filer(self):
        """Alle XML-filer under static/src — der QWeb-malene bor."""
        her = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rot = os.path.join(her, "static", "src")
        ut = []
        for mappe, _und, filer in os.walk(rot):
            for f in filer:
                if f.endswith(".xml"):
                    ut.append(os.path.join(mappe, f))
        return ut

    def test_ingen_python_operatorer_i_qweb_uttrykk(self):
        """🔑 Fanger `not`, `True`, `None` osv. i QWeb — de blir variabelnavn i JS.

        Denne testen ville fanget feilen som drepte styringsflaten 23.07,
        FØR den nådde nettleseren.
        """
        filer = self._mal_filer()
        self.assertTrue(filer, "Fant ingen QWeb-maler — testen måler da ingenting.")

        funn = []
        for sti in filer:
            with open(sti, encoding="utf-8") as fh:
                innhold = fh.read()
            # Fjern XML-kommentarer først: forklaringen på HVORFOR `not` er
            # forbudt inneholder selv ordet, og skal ikke gi falsk alarm.
            uten_kommentar = re.sub(r"<!--.*?-->", "", innhold, flags=re.S)

            for uttrykk in self.UTTRYKKS_ATTR.findall(uten_kommentar):
                for monster, navn, rad in self.FORBUDT:
                    if re.search(monster, uttrykk):
                        funn.append("%s: «%s» i «%s» — %s"
                                    % (os.path.basename(sti), navn, uttrykk.strip()[:70], rad))

        self.assertEqual(
            funn, [],
            "Python-syntaks i QWeb-uttrykk. Malen kompileres først i nettleseren, "
            "så ingen annen test fanger dette — men flaten blir HELT DØD:\n  "
            + "\n  ".join(funn))

    def test_malene_er_velformet_xml(self):
        """En uparsbar mal gir blank flate uten noe i serverloggen."""
        from xml.etree import ElementTree
        for sti in self._mal_filer():
            try:
                ElementTree.parse(sti)
            except ElementTree.ParseError as e:
                self.fail("%s er ikke velformet XML: %s" % (os.path.basename(sti), e))

    def test_ingen_if_i_inline_hendelser(self):
        """`if (…)` inne i t-on-* kompilerer ikke — hele malen dør.

        Kjent felle i huset: XML-validering fanger den IKKE, fordi filen er
        velformet. Bruk en metode på komponenten i stedet.
        """
        funn = []
        for sti in self._mal_filer():
            with open(sti, encoding="utf-8") as fh:
                uten_kommentar = re.sub(r"<!--.*?-->", "", fh.read(), flags=re.S)
            for m in re.finditer(r"""t-on-\w+\s*=\s*["']([^"']*)["']""", uten_kommentar):
                if re.search(r"\bif\s*\(", m.group(1)):
                    funn.append("%s: %s" % (os.path.basename(sti), m.group(1)[:60]))
        self.assertEqual(funn, [], "`if (` i inline t-on-* — malen kompilerer ikke:\n  "
                                   + "\n  ".join(funn))
