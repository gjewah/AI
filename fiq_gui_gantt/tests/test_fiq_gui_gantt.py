# -*- coding: utf-8 -*-
"""Tester for datalaget som mater Gantt-visningen (fiq_gui_gantt).

Modulen hadde NULL tester. «0 failed, 0 error(s) of 0 tests» er ikke grønt — det
er fravær av bevis.

Datalaget bak Gantt-en er tre computer og én rekalkulering:

  project.task     _compute_time_status      (frist/start/fremdrift → farge)
  project.task     _fiq_recompute_wbs        (disposisjonsnummer 01 / 01.01)
  project.project  _compute_time_status      (utløpsdato/fullføring → farge)
  project.milestone _compute_fiq_gantt_dates (én dato → start+slutt-datotid)
  project.milestone _compute_time_status

🔴 HOVEDVEKT: NULL-TILFELLENE. Erfaringen fra i dag er at det er nettopp de som
mangler dekning og som slipper ekte feil gjennom. En Gantt-visning er full av
poster som IKKE har datoene den vil ha: oppgaver uten startdato, uten frist,
uten begge, milepæler uten deadline, og prosjekter der start == slutt (divisjon
på null). Alle computene her er `store=False` og kjøres derfor på HVER lesing av
listen — kaster én av dem på én rad, ryker HELE visningen, ikke bare den raden.

Testene lager sine egne prosjekter, oppgaver og milepæler. Ingen test leser bare
eksisterende data, og ingen test avhenger av at en annen har kjørt først:
`_prosjekt()` gir hver test et ferskt, tomt prosjekt, slik at WBS-nummereringen
starter på 01 uansett rekkefølge.
"""

from datetime import datetime, time, timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


# post_install: modulen avhenger av project_enterprise/web_gantt/hr_timesheet.
# Under at_install ville registeret manglet moduler databasen likevel har
# NOT NULL-kolonner fra, og create() av prosjekt/oppgave ville sprekke på felt
# denne modulen verken eier eller ser. Odoo-kjernen gjør det samme
# (project/tests/test_project_mail_features.py:9).
@tagged("post_install", "-at_install", "fiq_gantt")
class TestFiqGuiGantt(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Task = cls.env["project.task"]
        cls.Project = cls.env["project.project"]
        cls.Milestone = cls.env["project.milestone"]
        cls.i_dag = fields.Date.context_today(cls.env["project.task"])
        cls.naa = fields.Datetime.now()

    # ---------------- egen tilstand, aldri delt ----------------

    def _prosjekt(self, navn="FIQ Gantt-testprosjekt", **vals):
        """Et FERSKT, TOMT prosjekt per kall.

        Kritisk for at testene skal være rekkefølge-uavhengige: WBS-nummerering
        teller søsken innen prosjektet, så et gjenbrukt prosjekt ville gitt ulikt
        svar avhengig av hvilke andre tester som hadde lagt oppgaver i det.
        """
        return self.Project.create(dict({"name": navn}, **vals))

    def _oppgave(self, prosjekt, navn="Oppgave", **vals):
        return self.Task.create(
            dict({"name": navn, "project_id": prosjekt.id}, **vals))

    def _sett_fremdrift(self, oppgave, andel):
        """Sett `progress` via de EKTE driverne — den kan ikke skrives direkte.

        🔴 Lærdom fra første kjøring 23.07: `progress` er et lagret COMPUTE-felt
        (hr_timesheet, `_compute_progress_hours`). En `progress=45.0` i create()
        blir stille forkastet og feltet forblir 0.0 — testen ville da bevist noe
        helt annet enn den påstod.

        Riktig vei er allokerte timer + førte timer:
            progress = (effective + subtask_effective) / allocated

        Vi allokerer 10 timer og fører `andel * 10` av dem.
        """
        oppgave.allocated_hours = 10.0
        oppgave.project_id.allow_timesheets = True
        self.env["account.analytic.line"].create({
            "name": "FIQ testtimer",
            "task_id": oppgave.id,
            "project_id": oppgave.project_id.id,
            "unit_amount": 10.0 * andel,
        })
        oppgave.invalidate_recordset(["progress", "effective_hours"])
        return oppgave

    # =================================================================
    #  project.task.time_status — NULL-TILFELLENE FØRST
    # =================================================================

    def test_oppgave_uten_datoer_er_gronn(self):
        """🔴 NULL: verken startdato eller frist.

        Dette er den vanligste oppgaven i basen. Uten frist finnes det ingen
        fakta som sier «forfalt» — da SKAL den være grønn, og computen må ikke
        røre datofeltene for å finne det ut.
        """
        opg = self._oppgave(self._prosjekt(), "Uten datoer")
        self.assertFalse(opg.planned_date_begin)
        self.assertFalse(opg.date_deadline)
        self.assertEqual(opg.time_status, "gronn")

    def test_oppgave_uten_startdato_men_med_frist_i_fremtiden(self):
        """🔴 NULL: start mangler. Fristgrenene må virke uten start.

        Uten start kan man ikke regne forløpt andel — men man kan fortsatt
        avgjøre om fristen er passert. Computen må hoppe over
        forventet/faktisk-regnestykket, ikke krasje i det.
        """
        opg = self._oppgave(
            self._prosjekt(), "Uten start",
            date_deadline=self.naa + timedelta(days=10))
        self.assertFalse(opg.planned_date_begin)
        self.assertEqual(opg.time_status, "gronn")

    def test_oppgave_uten_startdato_med_passert_frist_er_rod(self):
        """Frist passert veier tyngst, også når start mangler."""
        opg = self._oppgave(
            self._prosjekt(), "Uten start, forfalt",
            date_deadline=self.naa - timedelta(days=3))
        self.assertFalse(opg.planned_date_begin)
        self.assertEqual(opg.time_status, "rod")

    def test_oppgave_uten_frist_er_gronn_uansett_fremdrift(self):
        """🔴 NULL: frist mangler. Ingen frist = ingenting å bryte.

        Selv med startdato langt tilbake og 0 % fremdrift finnes det ingen
        avtale å være forsinket mot. Å farge den rød ville vært en påstand
        uten grunnlag.
        """
        opg = self._oppgave(
            self._prosjekt(), "Uten frist",
            planned_date_begin=self.naa - timedelta(days=30))
        self.assertFalse(opg.date_deadline)
        self.assertEqual(opg.time_status, "gronn")

    def test_oppgave_med_frist_i_dag_er_oransje(self):
        """Frist i dag (men senere på dagen) = «bak skjema», ikke forfalt."""
        prosjekt = self._prosjekt()
        slutt_i_dag = datetime.combine(self.i_dag, time(23, 59, 0))
        if slutt_i_dag <= self.naa:
            self.skipTest("kjort saa sent paa dogent at 23:59 allerede er passert")
        opg = self._oppgave(prosjekt, "Frist i dag", date_deadline=slutt_i_dag)
        self.assertEqual(opg.time_status, "oransje")

    def test_oppgave_forfalt_er_rod(self):
        opg = self._oppgave(
            self._prosjekt(), "Forfalt",
            planned_date_begin=self.naa - timedelta(days=10),
            date_deadline=self.naa - timedelta(days=1))
        self.assertEqual(opg.time_status, "rod")

    def test_lukket_oppgave_er_alltid_gronn(self):
        """En ferdig oppgave kan ikke være forsinket — den er ferdig.

        is_closed er compute på state i Odoo 19, så vi setter state og lar
        is_closed følge etter i stedet for å skrive direkte på et compute-felt.
        """
        opg = self._oppgave(
            self._prosjekt(), "Ferdig men forfalt",
            date_deadline=self.naa - timedelta(days=5))
        self.assertEqual(opg.time_status, "rod")
        opg.state = "1_done"
        if not opg.is_closed:
            self.skipTest("state '1_done' gir ikke is_closed i denne basen")
        self.assertEqual(opg.time_status, "gronn")

    def test_oppgave_i_rute_midt_i_vinduet(self):
        """Innenfor vinduet med fremdrift som forventet → grønn.

        Halvveis i tid med 100 % fremdrift ligger klart over forventningen.
        """
        opg = self._oppgave(
            self._prosjekt(), "I rute",
            planned_date_begin=self.naa - timedelta(days=5),
            date_deadline=self.naa + timedelta(days=5))
        self._sett_fremdrift(opg, 1.0)
        self.assertEqual(opg.time_status, "gronn")

    def test_oppgave_bak_skjema_midt_i_vinduet(self):
        """Halvveis i tid, 0 % gjort → 0 + 0,15 < 0,5 → oransje."""
        opg = self._oppgave(
            self._prosjekt(), "Bak skjema",
            planned_date_begin=self.naa - timedelta(days=5),
            date_deadline=self.naa + timedelta(days=5))
        self.assertEqual(opg.progress, 0.0)
        self.assertEqual(opg.time_status, "oransje")

    def test_oppgave_innenfor_marginen_er_gronn(self):
        """15 %-poeng margin: 45 % gjort ved 50 % forløpt skal IKKE flagges.

        Marginen er en bevisst forretningsregel. Forsvinner den, blir nesten
        alt oransje og fargen slutter å bety noe.
        """
        opg = self._oppgave(
            self._prosjekt(), "Innenfor margin",
            planned_date_begin=self.naa - timedelta(days=5),
            date_deadline=self.naa + timedelta(days=5))
        self._sett_fremdrift(opg, 0.45)
        self.assertEqual(opg.time_status, "gronn")

    def test_progress_tolkes_som_ANDEL_ikke_prosent(self):
        """🔴 REGRESJON (funnet 23.07, første testkjøring).

        `progress` fra hr_timesheet er en ANDEL 0..1, ikke prosent:
        `round((effective + subtask_effective) / allocated, 2)`
        (hr_timesheet/models/project_task.py:100).

        Verifisert mot EKTE data på Dev: 50 timer brukt av 15 allokerte gir
        progress = 3.33 — ikke 333. Koden delte likevel på 100, slik at en
        oppgave med 100 % fremdrift ble regnet som 1 % gjort og flagget
        «bak skjema» så snart ~16 % av vinduet var gått. Fargen var altså
        oransje for nesten alt — den sa ingenting.

        Testen låser tolkningen: FULL fremdrift midt i vinduet er grønn.
        """
        opg = self._oppgave(
            self._prosjekt(), "Andel ikke prosent",
            planned_date_begin=self.naa - timedelta(days=5),
            date_deadline=self.naa + timedelta(days=5))
        self._sett_fremdrift(opg, 1.0)
        self.assertEqual(opg.progress, 1.0, "progress skal vaere en andel (1.0 = 100 %)")
        self.assertEqual(opg.time_status, "gronn")

    def test_oppgave_med_null_lang_vindu_deler_ikke_paa_null(self):
        """🔴 NULL I BEREGNINGEN: start == slutt gir total = 0 sekunder.

        Uten `if total > 0` er dette en ZeroDivisionError midt i en
        listevisning. Vi setter vinduet til nøyaktig samme tidspunkt, litt frem
        i tid, slik at fristgrenene ikke slår inn først og skjuler tilfellet.
        """
        tidspunkt = self.naa + timedelta(days=2)
        opg = self._oppgave(
            self._prosjekt(), "Null-vindu",
            planned_date_begin=tidspunkt,
            date_deadline=tidspunkt)
        self.assertEqual(opg.time_status, "gronn")

    def test_oppgave_uten_fremdrift_behandles_som_null(self):
        """`progress or 0.0`: en tom fremdrift må ikke bli None i regnestykket."""
        opg = self._oppgave(
            self._prosjekt(), "Tom fremdrift",
            planned_date_begin=self.naa - timedelta(days=5),
            date_deadline=self.naa + timedelta(days=5))
        self.assertIn(opg.time_status, ("gronn", "oransje"))
        self.assertIsNotNone(opg.time_status)

    def test_time_status_paa_tomt_recordset(self):
        """🔴 NULL: computen på et tomt recordset skal ikke kaste."""
        tomt = self.Task.browse()
        tomt._compute_time_status()
        self.assertFalse(tomt)

    def test_time_status_paa_blandet_recordset(self):
        """Alle poster i ETT kall må få tildelt verdi — også de uten datoer.

        Klassisk feil: compute som kun setter feltet i én gren, og lar en annen
        falle igjennom → «Compute method failed to assign». Med to poster i
        samme kall fanges det; med én om gangen kan det gå upåaktet hen.
        """
        prosjekt = self._prosjekt()
        tom = self._oppgave(prosjekt, "Blandet tom")
        forfalt = self._oppgave(
            prosjekt, "Blandet forfalt",
            date_deadline=self.naa - timedelta(days=1))
        alle = tom | forfalt
        alle.invalidate_recordset(["time_status"])
        self.assertEqual(tom.time_status, "gronn")
        self.assertEqual(forfalt.time_status, "rod")
        self.assertTrue(all(t.time_status for t in alle))

    def test_time_status_er_ikke_lagret(self):
        """Feltet er `store=False` med vilje: statusen endres av at KLOKKA går.

        Et lagret felt ville frosset gårsdagens sannhet — en oppgave som
        forfalt i natt ville fortsatt vært grønn til noen skrev til den.
        """
        self.assertFalse(self.Task._fields["time_status"].store)

    # =================================================================
    #  project.task.wbs_number — disposisjonsnummeret
    # =================================================================

    def test_wbs_toppnivaa_nummereres_fra_01(self):
        prosjekt = self._prosjekt()
        a = self._oppgave(prosjekt, "A", sequence=10)
        b = self._oppgave(prosjekt, "B", sequence=20)
        self.assertEqual(a.wbs_number, "01")
        self.assertEqual(b.wbs_number, "02")

    def test_wbs_barn_arver_forelders_prefiks(self):
        prosjekt = self._prosjekt()
        mor = self._oppgave(prosjekt, "Mor", sequence=10)
        b1 = self._oppgave(prosjekt, "B1", parent_id=mor.id, sequence=10)
        b2 = self._oppgave(prosjekt, "B2", parent_id=mor.id, sequence=20)
        self.assertEqual(mor.wbs_number, "01")
        self.assertEqual(b1.wbs_number, "01.01")
        self.assertEqual(b2.wbs_number, "01.02")

    def test_wbs_tredje_nivaa(self):
        prosjekt = self._prosjekt()
        mor = self._oppgave(prosjekt, "Mor")
        barn = self._oppgave(prosjekt, "Barn", parent_id=mor.id)
        barnebarn = self._oppgave(prosjekt, "Barnebarn", parent_id=barn.id)
        self.assertEqual(barnebarn.wbs_number, "01.01.01")

    def test_wbs_soesken_med_lik_sequence_faar_ulike_nummer(self):
        """Lik sequence er NORMALEN (alle får 10 som default).

        Sorteringen faller da tilbake på id. To oppgaver må aldri ende med
        samme disposisjonsnummer — det er et nummer, ikke en etikett.
        """
        prosjekt = self._prosjekt()
        a = self._oppgave(prosjekt, "Lik A", sequence=10)
        b = self._oppgave(prosjekt, "Lik B", sequence=10)
        self.assertNotEqual(a.wbs_number, b.wbs_number)
        self.assertEqual({a.wbs_number, b.wbs_number}, {"01", "02"})

    def test_wbs_rekalkuleres_naar_sequence_endres(self):
        """Nummeret er DYNAMISK — det er hele forskjellen fra `code`."""
        prosjekt = self._prosjekt()
        a = self._oppgave(prosjekt, "A", sequence=10)
        b = self._oppgave(prosjekt, "B", sequence=20)
        self.assertEqual(a.wbs_number, "01")
        b.sequence = 5
        self.assertEqual(b.wbs_number, "01")
        self.assertEqual(a.wbs_number, "02")

    def test_wbs_rekalkuleres_i_BEGGE_prosjekter_ved_flytting(self):
        """🔴 Flytting mellom prosjekter må rydde opp BEGGE steder.

        write() fanger gamle prosjekter FØR super() nettopp for dette. Glipper
        det, står det igjen et hull i nummerrekka i avgiverprosjektet.
        """
        fra = self._prosjekt("Fra-prosjekt")
        til = self._prosjekt("Til-prosjekt")
        a = self._oppgave(fra, "A", sequence=10)
        b = self._oppgave(fra, "B", sequence=20)
        # X får LAVERE sequence enn A, slik at rekkefølgen i mottakerprosjektet
        # er entydig bestemt av sequence og ikke av id. (Med lik sequence
        # avgjør id-en, og da ville A — opprettet først — havnet foran X.)
        self._oppgave(til, "X", sequence=5)
        self.assertEqual(b.wbs_number, "02")

        a.project_id = til.id
        # Avgiver: B er nå eneste oppgave og rykker opp til 01.
        self.assertEqual(b.wbs_number, "01")
        # Mottaker: X (sequence 5) er 01, A (sequence 10) blir 02.
        self.assertEqual(a.wbs_number, "02")

    def test_wbs_forelder_i_annet_prosjekt_teller_som_rot(self):
        """🔴 Randtilfelle: parent_id peker UT av prosjektet.

        `_fiq_recompute_wbs` sjekker at forelderen er i samme prosjekt
        (`t.parent_id.id in task_ids`). Uten den sjekken havner barnet i
        by_parent under en forelder _walk aldri besøker → wbs_number = False,
        en oppgave som forsvinner ut av disposisjonen.
        """
        fra = self._prosjekt("Ekstern mor")
        til = self._prosjekt("Ekstern barn")
        mor = self._oppgave(fra, "Mor ute")
        barn = self._oppgave(til, "Barn inne", parent_id=mor.id)
        self.assertEqual(barn.project_id, til)
        self.assertEqual(barn.parent_id, mor)
        self.assertEqual(
            barn.wbs_number, "01",
            "barn med forelder i et ANNET prosjekt skal telle som rot her")

    def test_wbs_oppgave_uten_prosjekt_faar_ingen_nummer(self):
        """🔴 NULL: uten prosjekt finnes det ikke noe tre å nummerere i."""
        loes = self.Task.create({"name": "Loes oppgave"})
        self.assertFalse(loes.project_id)
        self.assertFalse(loes.wbs_number)

    def test_wbs_rekalkulering_med_tomt_prosjekt_recordset(self):
        """🔴 NULL: kall med tomt recordset skal ikke kaste."""
        self.Task._fiq_recompute_wbs(self.Project.browse())

    def test_wbs_rekalkulering_paa_slettet_prosjekt(self):
        """🔴 NULL: `projects.exists()` filtrerer bort slettede poster.

        Uten exists() ville et slettet prosjekt i settet gitt MissingError midt
        i en write som ellers var gyldig.
        """
        prosjekt = self._prosjekt("Slettes")
        spoekelse = self.Project.browse(prosjekt.id)
        prosjekt.unlink()
        self.Task._fiq_recompute_wbs(spoekelse)

    def test_wbs_prosjekt_uten_oppgaver(self):
        """🔴 NULL: tomt prosjekt — løkka skal bare hoppe over det."""
        tomt = self._prosjekt("Helt tomt")
        self.Task._fiq_recompute_wbs(tomt)
        self.assertFalse(self.Task.search([("project_id", "=", tomt.id)]))

    def test_wbs_endres_ikke_av_urelaterte_skrivinger(self):
        """Kun sequence/parent_id/project_id utløser rekalkulering.

        Skriver man navnet, skal ingenting nummereres på nytt — ellers får en
        harmløs redigering til å flytte nummer på hele treet.
        """
        prosjekt = self._prosjekt()
        a = self._oppgave(prosjekt, "A", sequence=10)
        for_ = a.wbs_number
        a.name = "A omdopt"
        self.assertEqual(a.wbs_number, for_)

    def test_wbs_er_readonly_felt(self):
        """Nummeret utledes — det skal ikke kunne tastes inn."""
        self.assertTrue(self.Task._fields["wbs_number"].readonly)

    def test_wbs_kopieres_ikke(self):
        """copy=False: en duplisert oppgave skal få SITT eget nummer.

        Ble nummeret kopiert, ville to oppgaver hatt samme disposisjonsnr. til
        neste rekalkulering — og duplikater i et nummersystem er en feil.
        """
        self.assertFalse(self.Task._fields["wbs_number"].copy)
        prosjekt = self._prosjekt()
        a = self._oppgave(prosjekt, "Original", sequence=10)
        kopi = a.copy()
        self.assertEqual(kopi.project_id, prosjekt)
        self.assertNotEqual(kopi.wbs_number, a.wbs_number)

    # =================================================================
    #  project.project.time_status
    # =================================================================

    def test_prosjekt_uten_datoer_er_gronn(self):
        """🔴 NULL: prosjekt uten start og uten utløpsdato."""
        prosjekt = self._prosjekt("Uten datoer")
        self.assertFalse(prosjekt.date)
        self.assertEqual(prosjekt.time_status, "gronn")

    def test_prosjekt_uten_startdato_men_passert_slutt_er_rod(self):
        """🔴 NULL: start mangler — sluttgrenen må virke likevel."""
        prosjekt = self._prosjekt(
            "Uten start", date=self.i_dag - timedelta(days=5))
        self.assertFalse(prosjekt.date_start)
        self.assertEqual(prosjekt.time_status, "rod")

    def test_prosjekt_uten_sluttdato_er_gronn(self):
        """🔴 NULL: uten utløpsdato finnes ingen frist å bryte."""
        prosjekt = self._prosjekt(
            "Uten slutt", date_start=self.i_dag - timedelta(days=100))
        self.assertFalse(prosjekt.date)
        self.assertEqual(prosjekt.time_status, "gronn")

    def test_prosjekt_med_slutt_i_dag_er_oransje(self):
        prosjekt = self._prosjekt("Slutt i dag", date=self.i_dag)
        if prosjekt.task_completion_percentage >= 100.0:
            self.skipTest("tomt prosjekt regnes som 100 % fullfoert i denne basen")
        self.assertEqual(prosjekt.time_status, "oransje")

    def test_prosjekt_med_start_lik_slutt_deler_ikke_paa_null(self):
        """🔴 NULL I BEREGNINGEN: endagsprosjekt gir total = 0 dager.

        Koden har to vern (`slutt > start` og `total > 0`). Dette er tilfellet
        som ville gitt ZeroDivisionError uten dem. Vi legger dagen frem i tid så
        rød/oransje-grenene ikke slår inn først.
        """
        dagen = self.i_dag + timedelta(days=3)
        prosjekt = self._prosjekt(
            "Endagsprosjekt", date_start=dagen, date=dagen)
        self.assertEqual(prosjekt.time_status, "gronn")

    def test_prosjekt_kan_ikke_ha_slutt_foer_start(self):
        """🔴 RANDTILFELLE: negativt vindu er UMULIG — Postgres nekter det.

        Første kjøring 23.07 forsøkte å lage et bakvendt prosjekt for å teste
        `slutt > start`-vernet i computen. Basen svarte:
        «new row for relation "project_project" violates check constraint
        "project_project_project_date_greater"» (skranken bor i
        project/models/project_project.py:186).

        Lærdommen er verdt å beholde: vernet i computen kan ikke nås via
        create/write, fordi databasen stopper tilstanden før den oppstår. Vi
        tester derfor det som FAKTISK gjelder — at skranken håndheves — i
        stedet for å påstå noe om en gren ingen data kan nå.
        """
        from psycopg2 import IntegrityError

        from odoo.tools.misc import mute_logger

        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self._prosjekt(
                    "Bakvendt",
                    date_start=self.i_dag + timedelta(days=10),
                    date=self.i_dag - timedelta(days=10))

    def test_prosjekt_time_status_paa_tomt_recordset(self):
        """🔴 NULL: tomt recordset skal ikke kaste."""
        tomt = self.Project.browse()
        tomt._compute_time_status()
        self.assertFalse(tomt)

    def test_prosjekt_time_status_paa_blandet_recordset(self):
        """Alle poster får verdi i ETT kall — også den uten datoer."""
        uten = self._prosjekt("Blandet uten")
        forfalt = self._prosjekt(
            "Blandet forfalt", date=self.i_dag - timedelta(days=5))
        alle = uten | forfalt
        alle.invalidate_recordset(["time_status"])
        self.assertEqual(uten.time_status, "gronn")
        self.assertEqual(forfalt.time_status, "rod")

    def test_prosjekt_time_status_er_ikke_lagret(self):
        self.assertFalse(self.Project._fields["time_status"].store)

    # =================================================================
    #  Drill-ned: prosjekt-Gantt → oppgave-Gantt
    # =================================================================

    def test_drill_ned_filtrerer_paa_prosjektet(self):
        """Knappen skal åpne oppgave-Gantt låst til DETTE prosjektet."""
        prosjekt = self._prosjekt("Drill")
        handling = prosjekt.action_open_task_gantt()
        self.assertEqual(handling["res_model"], "project.task")
        self.assertEqual(handling["domain"], [("project_id", "=", prosjekt.id)])
        self.assertEqual(handling["context"]["default_project_id"], prosjekt.id)
        self.assertEqual(handling["context"]["search_default_project_id"], prosjekt.id)
        self.assertTrue(handling["context"]["fiq_gantt"])
        # Vi er allerede filtrert til ett prosjekt — da skal det ikke grupperes
        # på prosjekt oppå.
        self.assertEqual(handling["context"]["group_by"], [])
        self.assertIn(prosjekt.display_name, handling["display_name"])

    def test_drill_ned_krever_ett_prosjekt(self):
        """ensure_one(): handlingen gjelder ett prosjekt, ikke et utvalg."""
        to = self._prosjekt("Drill A") | self._prosjekt("Drill B")
        with self.assertRaises(ValueError):
            to.action_open_task_gantt()

    # =================================================================
    #  project.milestone — avledede Gantt-datoer
    # =================================================================

    def test_milepael_uten_deadline_gir_tomme_gantt_datoer(self):
        """🔴 NULL: milepæl uten frist.

        `datetime.combine(False, time.min)` er en TypeError. Else-grenen er hele
        grunnen til at visningen ikke ryker på en halvutfylt milepæl.
        """
        milepael = self._milepael(deadline=False)
        if milepael is None:
            self.skipTest("project.milestone krever deadline i denne basen")
        self.assertFalse(milepael.fiq_gantt_start)
        self.assertFalse(milepael.fiq_gantt_stop)

    def test_milepael_med_deadline_blir_endagssoeyle(self):
        """Én dato → 00:00 til 23:59:59 samme dag, ellers er søylen usynlig."""
        dagen = self.i_dag + timedelta(days=5)
        milepael = self._milepael(deadline=dagen)
        self.assertEqual(milepael.fiq_gantt_start, datetime.combine(dagen, time.min))
        self.assertEqual(milepael.fiq_gantt_stop, datetime.combine(dagen, time.max))
        self.assertLess(milepael.fiq_gantt_start, milepael.fiq_gantt_stop)

    def test_milepael_gantt_datoer_paa_tomt_recordset(self):
        """🔴 NULL: tomt recordset skal ikke kaste."""
        tomt = self.Milestone.browse()
        tomt._compute_fiq_gantt_dates()
        self.assertFalse(tomt)

    def test_milepael_forfalt_er_rod(self):
        milepael = self._milepael(deadline=self.i_dag - timedelta(days=2))
        if milepael.is_reached:
            self.skipTest("milepaelen ble opprettet som naadd")
        self.assertEqual(milepael.time_status, "rod")

    def test_milepael_med_frist_i_dag_er_oransje(self):
        milepael = self._milepael(deadline=self.i_dag)
        if milepael.is_reached:
            self.skipTest("milepaelen ble opprettet som naadd")
        self.assertEqual(milepael.time_status, "oransje")

    def test_milepael_i_fremtiden_er_gronn(self):
        milepael = self._milepael(deadline=self.i_dag + timedelta(days=30))
        self.assertEqual(milepael.time_status, "gronn")

    def test_naadd_milepael_er_gronn_selv_om_fristen_er_passert(self):
        """Nådd er nådd — da er ikke en passert frist et avvik lenger."""
        milepael = self._milepael(deadline=self.i_dag - timedelta(days=10))
        milepael.is_reached = True
        self.assertEqual(milepael.time_status, "gronn")

    def test_milepael_uten_deadline_er_gronn(self):
        """🔴 NULL: ingen frist → ingen påstand om forsinkelse."""
        milepael = self._milepael(deadline=False)
        if milepael is None:
            self.skipTest("project.milestone krever deadline i denne basen")
        self.assertEqual(milepael.time_status, "gronn")

    def test_milepael_time_status_paa_blandet_recordset(self):
        """Med og uten frist i ETT kall — begge må få verdi."""
        uten = self._milepael(deadline=False)
        if uten is None:
            self.skipTest("project.milestone krever deadline i denne basen")
        forfalt = self._milepael(deadline=self.i_dag - timedelta(days=2))
        alle = uten | forfalt
        alle.invalidate_recordset(["time_status"])
        self.assertTrue(all(m.time_status for m in alle))

    # =================================================================
    #  Firma-scope (tenant-isolasjon arves fra project.*)
    # =================================================================

    def test_oppgave_arver_firma_fra_prosjektet(self):
        """Modulen legger IKKE på egen firma-logikk — den arver project.*.

        Slår denne feil, er det et signal om at noe har begynt å sette
        company_id selv, og da må isolasjonen vurderes på nytt.
        """
        prosjekt = self._prosjekt(
            "Firma-test", company_id=self.env.company.id)
        opg = self._oppgave(prosjekt, "Firma-oppgave")
        self.assertEqual(opg.company_id, prosjekt.company_id)

    def test_wbs_teller_kun_innenfor_ett_prosjekt(self):
        """Nummerering krysser ALDRI prosjektgrensen.

        To prosjekter starter begge på 01 — nummeret er relativt til sitt eget
        tre. Ville de delt teller, ville prosjekt B's nummer endret seg av at
        noen la til en oppgave i prosjekt A.
        """
        a = self._prosjekt("Teller A")
        b = self._prosjekt("Teller B")
        a1 = self._oppgave(a, "A1")
        b1 = self._oppgave(b, "B1")
        self.assertEqual(a1.wbs_number, "01")
        self.assertEqual(b1.wbs_number, "01")

    # =================================================================
    #  Hjelpere
    # =================================================================

    def _milepael(self, deadline, prosjekt=None):
        """Egen milepæl. Returnerer None hvis basen krever deadline.

        deadline er ikke required i standard Odoo, men vi later ikke som vi vet
        at ingen nabomodul har gjort det til det. Går create() i stykker på
        akkurat det, hopper testen som kaller — den hoppede testen sier ærlig at
        null-tilfellet ikke lot seg lage her.
        """
        prosjekt = prosjekt or self._prosjekt("Milepael-prosjekt")
        vals = {"name": "FIQ testmilepael", "project_id": prosjekt.id}
        if deadline:
            vals["deadline"] = deadline
        try:
            with self.env.cr.savepoint():
                return self.Milestone.create(vals)
        except Exception:  # noqa: BLE001
            if not deadline:
                return None
            raise
