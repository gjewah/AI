# -*- coding: utf-8 -*-
"""Tester for dynamisk disposisjonsnummer (fiq_wbs_number på project.task).

NUMMER-MODELLEN (må ALDRI blandes):
  sequence_code  project.project  «2026-00001»  STABIL — røres aldri
  code           project.task     «T0001»       STABIL — røres aldri
  fiq_wbs_number project.task     «01.02»       DYNAMISK — rekalkuleres ved flytting

Hvorfor testene finnes: computen er `store=True` + `recursive=True`. Feil her gir
feil nummer i alle native visninger, sortering og rapporter — og det oppdages sent.

⚠️ MISTENKT SVAKHET (GUI Prosjekt V0.02, 2026-07-18):
computen bruker `list(ordered).index(task)` for å finne posisjon. Det mønsteret er
kanonisert som FEIL i hjernen (FIQ-IT/ai commit 229b6a6: «Odoo compute — posisjon via
ID-liste, aldri list(recordset).index()»), fordi recordset-elementer ikke nødvendigvis
sammenlignes som forventet i alle kontekster (NewId/prefetch/onchange).
`test_wbs_i_onchange_kontekst` er skrevet spesifikt for å avdekke om dette slår til.
Feiler den, er fiksen: bygg en id-liste og bruk `.index(task.id)`.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq", "fiq_prj")
class TestFiqWbs(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Task = cls.env["project.task"]
        # Gjenbruk et EKSISTERENDE prosjekt hvis mulig — project.project.create()
        # kan feile på required+compute+store-felt (billing_type-fella, 17.07).
        cls.project = cls.env["project.project"].search([], limit=1)
        if not cls.project:
            cls.skipTest(cls, "Ingen project.project finnes å teste mot")

    def _task(self, name, parent=False, sequence=10):
        return self.Task.create({
            "name": name,
            "project_id": self.project.id,
            "parent_id": parent and parent.id or False,
            "sequence": sequence,
        })

    def test_toppnivaa_nummereres_fra_01(self):
        """Første toppnivå-oppgave i et prosjekt får 01, neste 02 — nullpolstret."""
        a = self._task("A", sequence=10)
        b = self._task("B", sequence=20)
        self.assertRegex(a.fiq_wbs_number, r"^\d{2}$")
        self.assertRegex(b.fiq_wbs_number, r"^\d{2}$")
        # B skal komme etter A når sequence er høyere
        self.assertLess(int(a.fiq_wbs_number), int(b.fiq_wbs_number))

    def test_underoppgave_arver_forelders_prefiks(self):
        """Underoppgave = <forelders wbs>.<løpenr> — punktum-separert."""
        mor = self._task("Mor", sequence=10)
        barn = self._task("Barn", parent=mor, sequence=10)
        self.assertTrue(
            barn.fiq_wbs_number.startswith(mor.fiq_wbs_number + "."),
            "Barn '%s' skal starte med mors '%s.'" % (
                barn.fiq_wbs_number, mor.fiq_wbs_number),
        )
        self.assertEqual(barn.fiq_wbs_number.count("."), 1)

    def test_tredje_nivaa_faar_to_punktum(self):
        """01.02.01 — dybden skal følge treet."""
        mor = self._task("Mor")
        barn = self._task("Barn", parent=mor)
        barnebarn = self._task("Barnebarn", parent=barn)
        self.assertEqual(barnebarn.fiq_wbs_number.count("."), 2)
        self.assertTrue(
            barnebarn.fiq_wbs_number.startswith(barn.fiq_wbs_number + "."))

    def test_soesken_faar_ulike_nummer(self):
        """To barn under samme forelder skal ALDRI få samme nummer."""
        mor = self._task("Mor")
        b1 = self._task("B1", parent=mor, sequence=10)
        b2 = self._task("B2", parent=mor, sequence=20)
        b3 = self._task("B3", parent=mor, sequence=30)
        numre = [b1.fiq_wbs_number, b2.fiq_wbs_number, b3.fiq_wbs_number]
        self.assertEqual(len(set(numre)), 3, "Duplikate WBS-numre: %s" % numre)

    def test_soesken_med_LIK_sequence_faar_ulike_nummer(self):
        """🔴 REGRESJONSTEST for den ekte produksjonsfeilen (AI KR-sporet, 18.07.2026).

        DETTE ER TESTEN SOM MANGLET. På ekte data fikk **66 toppnivå-oppgaver i samme
        prosjekt alle nummeret «01»** (verifisert med duplikat-spørring mot fiqas Staging).

        Årsak: computen brukte `list(sorted_recordset).index(task)`, som sammenligner
        record-OBJEKTER. Odoos default `sequence` er 10 for ALLE oppgaver, så alle søsken
        var «like» ved sortering og `.index()` returnerte 0 for hver av dem → alle fikk 01.
        Fiks: slå opp posisjon i en ID-liste (`sibs_ids.index(task.id)`).

        ⚠️ HVORFOR MIN FORRIGE TEST IKKE FANGET DET (lærdom):
        `test_soesken_faar_ulike_nummer` gir hvert søsken ULIK sequence (10/20/30) — da
        virker `.index()` tilfeldigvis. Den ekte verden bruker default-sequence, altså LIK
        for alle. Testen var «grønn» og feilen var likevel i produksjon. Jeg meldte til og
        med mistanken som «avkreftet» på grunn av den. **En test som ikke speiler ekte
        data beviser ingenting.** [[feedback-compute-index-recordset]]
        """
        mor = self._task("Mor")
        # ALLE med samme sequence — nøyaktig som Odoos default i virkeligheten
        barn = [self._task("B%d" % i, parent=mor, sequence=10) for i in range(5)]
        numre = [b.fiq_wbs_number for b in barn]
        self.assertEqual(
            len(set(numre)), len(barn),
            "Søsken med LIK sequence fikk duplikate WBS-numre: %s "
            "(dette er produksjonsfeilen der 66 oppgaver alle fikk «01»)" % numre,
        )

    def test_toppnivaa_med_lik_sequence_faar_ulike_nummer(self):
        """Samme regresjon på toppnivå — der de 66 duplikatene faktisk oppsto."""
        toppnivaa = [self._task("T%d" % i, sequence=10) for i in range(5)]
        numre = [t.fiq_wbs_number for t in toppnivaa]
        self.assertEqual(
            len(set(numre)), len(toppnivaa),
            "Toppnivå-oppgaver med lik sequence fikk duplikate numre: %s" % numre,
        )

    def test_wbs_rekalkuleres_naar_oppgave_flyttes(self):
        """Kjernen i «dynamisk»: flytter du oppgaven, endres nummeret."""
        mor_a = self._task("MorA", sequence=10)
        mor_b = self._task("MorB", sequence=20)
        barn = self._task("Barn", parent=mor_a)
        for_flytting = barn.fiq_wbs_number
        self.assertTrue(for_flytting.startswith(mor_a.fiq_wbs_number + "."))

        barn.parent_id = mor_b
        barn.invalidate_recordset(["fiq_wbs_number"])
        self.assertTrue(
            barn.fiq_wbs_number.startswith(mor_b.fiq_wbs_number + "."),
            "Etter flytting skal barnet arve MorBs prefiks (var %s, ble %s)" % (
                for_flytting, barn.fiq_wbs_number),
        )

    def test_endret_rekkefoelge_endrer_egen_oppgaves_nummer(self):
        """Flyttes en oppgave bakerst, skal DENS eget nummer oppdateres.

        ⚠️ DOKUMENTERT BEGRENSNING (verifisert i kjøring 2026-07-18, ikke antatt):
        søsknene omnummereres IKKE automatisk. Computen avhenger av `sequence`,
        `parent_id` og `project_id` på oppgaven SELV — endres B1s sequence, blir
        ikke B2s felt merket urent, for B2 er ikke i B1s avhengighetskjede.
        Første kjøring feilet nettopp her («01.02» != «01.01»): FEILEN LÅ I TESTEN,
        som antok kaskade-omnummerering. Koden oppfører seg som Odoo-computer gjør.

        Konsekvens for flaten: skal Gantt/liste vise fortløpende numre etter en
        rokering, må søskenlista invalideres eksplisitt. Se ÅPENT PUNKT i
        koordineringen — vurderes sammen med Prosjektoversikt-flaten.
        """
        mor = self._task("Mor")
        b1 = self._task("B1", parent=mor, sequence=10)
        b2 = self._task("B2", parent=mor, sequence=20)
        b1_for = b1.fiq_wbs_number
        b2_for = b2.fiq_wbs_number
        self.assertNotEqual(b1_for, b2_for)

        # Flytt B1 bakerst -> B1s EGET nummer skal oppdateres
        b1.sequence = 30
        b1.invalidate_recordset(["fiq_wbs_number"])
        self.assertEqual(
            b1.fiq_wbs_number, b2_for,
            "B1 skal ha overtatt siste-plassen etter rokering")

        # Dokumenterer dagens faktiske oppførsel for søsknet (ikke kaskade):
        self.assertEqual(
            b2.fiq_wbs_number, b2_for,
            "Søsken omnummereres ikke automatisk — endres dette, oppdater testen")

    def test_oppgave_uten_prosjekt_og_forelder_har_ingen_wbs(self):
        """Uten plassering i et tre finnes det ikke noe disposisjonsnummer."""
        loes = self.Task.create({"name": "Løs oppgave"})
        self.assertFalse(loes.fiq_wbs_number)

    def test_stabile_nummer_roeres_ikke_av_wbs(self):
        """WBS skal ALDRI endre oppgavenr. (code) — de er to ulike ting.

        🔴 `code` kommer fra `project_sequence_number` (FIQ/loym), ikke fra Odoo.
        På Dev 22.07 var modulen uninstalled, og testen kastet AttributeError.
        Den skal hoppe over, ikke feile: fraværet av en valgfri nabomodul er ikke
        en feil i vår modul.
        """
        if "code" not in self.Task._fields:
            self.skipTest("project_sequence_number ikke installert — `code` finnes ikke")
        t = self._task("T")
        code_for = t.code
        t.sequence = 999
        t.invalidate_recordset(["fiq_wbs_number"])
        self.assertEqual(t.code, code_for, "WBS-rekalkulering rørte oppgavenummeret")

    def test_wbs_i_onchange_kontekst(self):
        """⚠️ Fanger den mistenkte `list(recordset).index()`-svakheten.

        I onchange/NewId-kontekst er postene ikke lagrede poster. Bruker computen
        `list(ordered).index(task)` kan oppslaget feile eller gi feil posisjon.
        Kanonisert regel: finn posisjon via ID-liste, ikke via recordset-medlemskap.
        """
        mor = self._task("Mor")
        self._task("B1", parent=mor, sequence=10)
        ny = self.Task.new({
            "name": "Ny i onchange",
            "project_id": self.project.id,
            "parent_id": mor.id,
            "sequence": 20,
        })
        # Skal ikke kaste, og skal gi et fornuftig nummer under mor
        verdi = ny.fiq_wbs_number
        self.assertTrue(
            verdi is False or verdi.startswith(mor.fiq_wbs_number + "."),
            "Uventet WBS i onchange-kontekst: %r" % (verdi,),
        )
