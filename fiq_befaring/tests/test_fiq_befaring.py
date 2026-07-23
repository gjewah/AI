# -*- coding: utf-8 -*-
"""Tester for befarings-broen (fiq.befaring + .rom + .funn).

Hvorfor de finnes (2026-07-23): modulen hadde NULL tester på 262 linjer
forretningslogikk — `--test-enable` ga «0 failed, 0 error(s) of 0 tests», som
ser grønt ut og beviser ingenting. Nå skal to spor bygge videre på samme modell
samtidig: Salg eier alt FØR `state = overfort`, Prosjekt eier alt etter. Da er
tilstandskjeden og feltansvaret en KONTRAKT mellom to spor, ikke en detalj.

Kanon som styrer testene:
  * Hver test OPPRETTER sin egen tilstand (lead, befaring, rom, funn). Ingen
    påstand her avhenger av hva som tilfeldigvis ligger i basen — en test som
    leser Dev-demodata beviser ingenting om koden.
  * Tenant-isolasjon: `company_id` arves fra salgsmuligheten, aldri gjettes.
  * `populer_kalkulator_data()` er SKRIVFRI — den returnerer kandidat-linjer;
    selve skrivingen eier bransje-/kalkulator-overlaget.
"""

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq_befaring")
class TestFiqBefaring(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Befaring = cls.env["fiq.befaring"]
        cls.Rom = cls.env["fiq.befaring.rom"]
        cls.Funn = cls.env["fiq.befaring.funn"]
        cls.Lead = cls.env["crm.lead"]
        cls.Task = cls.env["project.task"]
        cls.Project = cls.env["project.project"]
        cls.Partner = cls.env["res.partner"]

        cls.company = cls.env.company
        cls.kunde = cls.Partner.create({"name": "TEST Kunde Befaring AS"})

    # ------------------------------------------------------------ hjelpere
    #
    # Alt under bygger sin EGEN tilstand. `_lag_lead` og `_lag_befaring` er de
    # eneste stedene som rører basen for oppsett, slik at en endring i
    # påkrevde felt bare må rettes ett sted.

    def _lag_lead(self, **vals):
        return self.Lead.create(dict({
            "name": "TEST Salgsmulighet befaring",
            "partner_id": self.kunde.id,
            "company_id": self.company.id,
        }, **vals))

    def _lag_befaring(self, **vals):
        return self.Befaring.create(dict({
            "name": "TEST Befaring",
            "company_id": self.company.id,
        }, **vals))

    def _lag_rom(self, befaring, **vals):
        return self.Rom.create(dict({
            "befaring_id": befaring.id,
            "name": "Stue",
        }, **vals))

    def _lag_prosjekt(self, **vals):
        return self.Project.create(dict({
            "name": "TEST Prosjekt befaring",
            "company_id": self.company.id,
        }, **vals))

    # ==================================================================
    # opprett_fra_lead — inngangen fra salgsprosessen
    # ==================================================================

    def test_opprett_fra_lead_lager_befaring_i_pagaar(self):
        """Broen inn fra salg: en befaring startet fra en salgsmulighet er
        allerede i gang — den skal ikke ligge i «Utkast» og vente.

        Statusen er ikke kosmetikk: `pagaar` er signalet til Salg om at
        befaringen er deres til `overfort` settes.
        """
        lead = self._lag_lead()
        bef_id = self.Befaring.opprett_fra_lead(lead.id)

        self.assertTrue(bef_id, "opprett_fra_lead ga ingen id")
        bef = self.Befaring.browse(bef_id)
        self.assertTrue(bef.exists(), "Befaringen ble ikke faktisk opprettet")
        self.assertEqual(bef.state, "pagaar")
        self.assertEqual(bef.lead_id, lead)
        self.assertEqual(bef.partner_id, self.kunde,
                         "Kunden skal arves fra salgsmuligheten")

    def test_opprett_fra_lead_arver_navnet_fra_salgsmuligheten(self):
        """Navn, ikke ID: befaringen skal kunne leses av et menneske.

        Standardnavnet peker på salgsmuligheten den kom fra — ellers står
        Gjermund med en liste «Ny befaring» × 14 og må åpne hver for å se
        hvilken kunde det gjelder.
        """
        lead = self._lag_lead(name="TEST Rehab Storgata 5")
        bef = self.Befaring.browse(self.Befaring.opprett_fra_lead(lead.id))
        self.assertIn("TEST Rehab Storgata 5", bef.name,
                      "Salgsmulighetens navn skal stå i befaringens navn")

    def test_opprett_fra_lead_respekterer_eksplisitt_navn(self):
        """Oppgir kalleren et navn, skal det brukes — ikke overstyres."""
        lead = self._lag_lead()
        bef = self.Befaring.browse(
            self.Befaring.opprett_fra_lead(lead.id, name="TEST Eget navn"))
        self.assertEqual(bef.name, "TEST Eget navn")

    def test_opprett_fra_lead_ukjent_lead_gir_False(self):
        """🔑 RANDTILFELLE: en id som ikke finnes skal gi False, ikke krasj.

        Kallet kommer fra en knapp/mobilflate der id-en kan være foreldet
        (leadet slettet eller slått sammen mens befareren var offline).
        `False` er et svar flaten kan håndtere; en exception er en blank skjerm.
        """
        self.assertFalse(
            self.Befaring.opprett_fra_lead(999999999),
            "Ukjent salgsmulighet skal gi False, ikke opprette noe",
        )

    def test_opprett_fra_lead_uten_kunde_gir_ingen_partner(self):
        """En salgsmulighet uten kunde skal ikke finne på en.

        `partner_id.id or False` — testen låser at vi ikke faller tilbake på
        noe «nærliggende». Tom kunde er ærligere enn feil kunde.
        """
        lead = self._lag_lead(partner_id=False)
        bef = self.Befaring.browse(self.Befaring.opprett_fra_lead(lead.id))
        self.assertFalse(bef.partner_id, "Kunde skal ikke gjettes")

    # ==================================================================
    # TENANT-ISOLASJON — company_id arves fra salgsmuligheten
    # ==================================================================

    def test_company_id_arves_fra_lead(self):
        """🔴 KRITISK: firmaet følger salgsmuligheten, ikke sesjonen.

        Uten dette havner befaringen i det firmaet befareren tilfeldigvis har
        aktivt i nettleseren — og record-rulene (`company_id in company_ids`)
        gjør den så usynlig for teamet som faktisk eier salget. Det er
        kryss-tenant-lekkasje i motsatt retning: data i feil firma.
        """
        annet = self.env["res.company"].create({"name": "TEST Firma B befaring"})
        # Sesjonen kjører i self.company; leadet tilhører «annet».
        lead = self._lag_lead(company_id=annet.id)
        bef = self.Befaring.browse(self.Befaring.opprett_fra_lead(lead.id))
        self.assertEqual(
            bef.company_id, annet,
            "Befaringen skal arve leadets firma (%s), ikke sesjonens (%s)"
            % (annet.name, self.company.name),
        )

    def test_company_id_faller_tilbake_til_sesjonen_uten_firma_paa_lead(self):
        """Lead uten firma: fall tilbake til aktivt firma, aldri til tomt.

        `company_id` er required — uten fallback ville kallet krasjet på et
        lead som (lovlig) står uten firma.
        """
        lead = self._lag_lead(company_id=False)
        bef = self.Befaring.browse(self.Befaring.opprett_fra_lead(lead.id))
        self.assertEqual(bef.company_id, self.env.company)

    def test_rom_og_funn_arver_firma_fra_befaringen(self):
        """company_id er related+store nedover — isolasjonen må følge linjene.

        Et rom eller funn som står uten firma ville sluppet gjennom
        record-rulens `('company_id', '=', False)`-gren og blitt synlig for
        ALLE firmaer. Derfor testes arven eksplisitt, ikke antas.
        """
        annet = self.env["res.company"].create({"name": "TEST Firma C befaring"})
        bef = self._lag_befaring(company_id=annet.id)
        rom = self._lag_rom(bef)
        funn = self.Funn.create({
            "befaring_id": bef.id, "rom_id": rom.id, "name": "Fuktskade",
        })
        self.assertEqual(rom.company_id, annet, "Rommet arvet ikke firmaet")
        self.assertEqual(funn.company_id, annet, "Funnet arvet ikke firmaet")

    # ==================================================================
    # _onchange_lead_id
    # ==================================================================

    def test_onchange_lead_id_setter_kunde(self):
        """Skjemaet skal fylle kunden når befareren velger salgsmulighet."""
        lead = self._lag_lead()
        bef = self._lag_befaring()
        bef.lead_id = lead
        bef._onchange_lead_id()
        self.assertEqual(bef.partner_id, self.kunde)

    def test_onchange_lead_id_uten_kunde_rorer_ikke_eksisterende(self):
        """🔑 En salgsmulighet uten kunde skal ikke TØMME en kunde som står der.

        Befareren kan ha satt kunden manuelt før han koblet på leadet.
        Onchangen legger til informasjon; den skal ikke slette noe.
        """
        lead = self._lag_lead(partner_id=False)
        bef = self._lag_befaring(partner_id=self.kunde.id)
        bef.lead_id = lead
        bef._onchange_lead_id()
        self.assertEqual(
            bef.partner_id, self.kunde,
            "Onchangen slettet en kunde befareren hadde satt selv",
        )

    def test_onchange_lead_id_uten_lead_er_trygg(self):
        """Tomt lead skal ikke krasje onchangen."""
        bef = self._lag_befaring()
        bef._onchange_lead_id()  # skal ikke kaste
        self.assertFalse(bef.lead_id)

    # ==================================================================
    # _compute_antall
    # ==================================================================

    def test_compute_antall_tom_befaring_er_null(self):
        """🔑 RANDTILFELLE: befaring uten rom skal gi 0, ikke tomt felt."""
        bef = self._lag_befaring()
        self.assertEqual(bef.rom_antall, 0)
        self.assertEqual(bef.funn_antall, 0)

    def test_compute_antall_teller_rom_og_funn(self):
        """Tallene på befaringen må stemme med linjene under.

        Ellers ser Gjermund «3 rom» og får opp 2 — den slags undergraver
        tilliten til hele flaten.
        """
        bef = self._lag_befaring()
        for i in range(3):
            self._lag_rom(bef, name="Rom %d" % i, sequence=10 + i)
        self.Funn.create([
            {"befaring_id": bef.id, "name": "Funn A"},
            {"befaring_id": bef.id, "name": "Funn B"},
        ])
        bef.invalidate_recordset(["rom_antall", "funn_antall"])
        self.assertEqual(bef.rom_antall, 3)
        self.assertEqual(bef.funn_antall, 2)

    def test_compute_antall_oppdateres_naar_rom_slettes(self):
        """Store compute må følge med når linjer forsvinner, ikke fryse."""
        bef = self._lag_befaring()
        rom = self._lag_rom(bef)
        self._lag_rom(bef, name="Bad")
        self.assertEqual(bef.rom_antall, 2)
        rom.unlink()
        bef.invalidate_recordset(["rom_antall"])
        self.assertEqual(bef.rom_antall, 1, "Telleren hang igjen etter sletting")

    # ==================================================================
    # rom.create — funn opprettet inline skal peke på befaringen
    # ==================================================================

    def test_rom_create_inline_funn_KREVER_eksplisitt_befaring_id(self):
        """🔴 EKTE FUNN 23.07 — første testkjøring avslørte DØD KODE.

        `fiq_befaring_rom.create()` har en fix-up-løkke (linje 45–48) som skal
        «sørge for at funn opprettet inline også peker på befaringen». Den
        løkka blir ALDRI nådd:

            null value in column "befaring_id" of relation
            "fiq_befaring_funn" violates not-null constraint

        `befaring_id` er `required=True` på `fiq.befaring.funn`, så databasen
        avviser raden INNE i `super().create(vals_list)` — altså FØR koden som
        skulle reparere den kjører. Reparasjonen kommer et steg for sent.

        🔑 Hvorfor dette betyr noe for begge spor: den som lager et funn
        inline under et rom i skjemavisningen får en rå SQL-feil i fjeset, ikke
        en forklaring. Koden SER ut som den håndterer tilfellet.

        Testen låser oppførselen slik den FAKTISK er i dag, så ingen tror
        løkka virker. Fikses den (f.eks. ved å sette `befaring_id` i vals FØR
        `super()`), skal denne testen snus til å kreve at kallet lykkes.
        Rettingen eies av sporene, ikke av testrunden — derfor dokumentert her.
        """
        from psycopg2.errors import NotNullViolation
        from odoo.tools.misc import mute_logger

        bef = self._lag_befaring()
        with self.assertRaises(NotNullViolation), mute_logger("odoo.sql_db"):
            with self.cr.savepoint():
                self.Rom.create({
                    "befaring_id": bef.id,
                    "name": "Kjøkken",
                    "funn_ids": [(0, 0, {"name": "Sprekk i flis", "type": "avvik"})],
                })

    def test_funn_med_eksplisitt_befaring_id_virker(self):
        """Veien som FAKTISK virker i dag: sett `befaring_id` selv.

        Motstykket til testen over — den viser at datamodellen er i orden;
        det er kun den inline fix-up-løkka som er død kode.
        """
        bef = self._lag_befaring()
        rom = self.Rom.create({
            "befaring_id": bef.id,
            "name": "Kjøkken",
            "funn_ids": [(0, 0, {
                "name": "Sprekk i flis", "type": "avvik",
                "befaring_id": bef.id,
            })],
        })
        self.assertEqual(len(rom.funn_ids), 1)
        self.assertEqual(rom.funn_ids.befaring_id, bef)
        bef.invalidate_recordset(["funn_ids", "funn_antall"])
        self.assertEqual(bef.funn_antall, 1,
                         "Inline funn telles ikke på befaringen")

    # ==================================================================
    # get_romskjema_data
    # ==================================================================

    def test_get_romskjema_data_tom_befaring(self):
        """🔑 RANDTILFELLE: befaring uten rom gir tom liste, ikke krasj/None.

        Romskjemaet genereres FØR befareren har vært på stedet — flaten må
        tåle den tilstanden uten å se ødelagt ut.
        """
        bef = self._lag_befaring()
        data = bef.get_romskjema_data()
        self.assertEqual(data["rom"], [])
        self.assertEqual(data["befaring"], bef.name)
        self.assertIn("kunde", data)
        self.assertIn("dato", data)

    def test_get_romskjema_data_rom_uten_funn(self):
        """🔑 RANDTILFELLE: et rom uten funn skal ha tom funn-liste.

        Et rom uten avvik er et helt normalt utfall av en befaring — det er
        faktisk det vi håper på. Skjemaet må vise rommet, ikke skjule det.
        """
        bef = self._lag_befaring()
        self._lag_rom(bef, name="Gang", etasje="1", areal=8.5)
        data = bef.get_romskjema_data()
        self.assertEqual(len(data["rom"]), 1)
        self.assertEqual(data["rom"][0]["rom"], "Gang")
        self.assertEqual(data["rom"][0]["funn"], [],
                         "Rom uten funn skal gi tom liste, ikke mangle nøkkelen")

    def test_get_romskjema_data_tar_med_funn_per_rom(self):
        """Funnene skal ligge under RIKTIG rom — ikke i en felles bøtte.

        Romskjemaet er dokumentet håndverkeren tar med ut. Et funn plassert i
        feil rom er verre enn et manglende funn.
        """
        bef = self._lag_befaring()
        stue = self._lag_rom(bef, name="Stue", sequence=10)
        bad = self._lag_rom(bef, name="Bad", sequence=20)
        self.Funn.create({
            "befaring_id": bef.id, "rom_id": bad.id,
            "name": "Fukt bak dusj", "type": "avvik", "alvorlighet": "hoy",
        })

        data = bef.get_romskjema_data()
        per_rom = {r["rom"]: r for r in data["rom"]}
        self.assertEqual(per_rom["Stue"]["funn"], [], "Stua har ingen funn")
        self.assertEqual(len(per_rom["Bad"]["funn"]), 1)
        self.assertEqual(per_rom["Bad"]["funn"][0]["alvorlighet"], "hoy")
        self.assertEqual(per_rom["Bad"]["funn"][0]["status"], "apen")
        self.assertNotIn(
            stue.id, [f.get("rom_id") for f in per_rom["Bad"]["funn"]],
            "Funn lekket mellom rom",
        )

    def test_get_romskjema_data_folger_sequence(self):
        """Rekkefølgen er befarerens rute gjennom bygget — den skal holdes.

        Sorteres det på id i stedet, hopper skjemaet mellom etasjer så snart
        et rom legges til i etterkant.
        """
        bef = self._lag_befaring()
        # Opprettes i «feil» rekkefølge: sequence skal likevel styre.
        self._lag_rom(bef, name="Loft", sequence=30)
        self._lag_rom(bef, name="Kjeller", sequence=10)
        self._lag_rom(bef, name="Stue", sequence=20)
        data = bef.get_romskjema_data()
        self.assertEqual(
            [r["rom"] for r in data["rom"]], ["Kjeller", "Stue", "Loft"],
            "Romskjemaet følger ikke sequence",
        )

    def test_get_romskjema_data_har_flerspraaklige_tiltak(self):
        """NO/EN lagres side om side — begge skal med i skjemaet.

        Flerspråklig lagring er poenget med `ai_tiltak_no`/`_en`: samme
        befaring skal kunne leses av et norsk og et engelsk arbeidslag.
        """
        bef = self._lag_befaring()
        self._lag_rom(bef, name="Bad", ai_tiltak_no="Rive flis",
                      ai_tiltak_en="Remove tiles")
        rad = bef.get_romskjema_data()["rom"][0]
        self.assertEqual(rad["ai_tiltak_no"], "Rive flis")
        self.assertEqual(rad["ai_tiltak_en"], "Remove tiles")

    def test_get_romskjema_data_tomme_felt_er_streng_ikke_False(self):
        """🔑 `False` i et skjema skrives ut som «False» i QWeb/Excel.

        Metoden er grunnlag for eksport. Tomme tekstfelt må være tom streng,
        ellers står ordet «False» i rutene på dokumentet håndverkeren får.
        """
        bef = self._lag_befaring()
        self._lag_rom(bef, name="Bod")
        rad = bef.get_romskjema_data()["rom"][0]
        for felt in ("etasje", "tiltak", "ai_tiltak_no", "ai_tiltak_en"):
            self.assertIsInstance(
                rad[felt], str,
                "«%s» er %r — tomme felt må være tom streng i eksporten"
                % (felt, rad[felt]),
            )

    def test_get_romskjema_data_dato_er_ren_datostreng(self):
        """Dato skal være «ÅÅÅÅ-MM-DD», ikke et Date-objekt eller tidsstempel."""
        bef = self._lag_befaring(dato=fields.Date.to_date("2026-07-23"))
        self.assertEqual(bef.get_romskjema_data()["dato"], "2026-07-23")

    def test_get_romskjema_data_krever_en_befaring(self):
        """`ensure_one()` — to befaringer i ett skjema ville blandet kunder."""
        b1 = self._lag_befaring()
        b2 = self._lag_befaring(name="TEST Befaring 2")
        with self.assertRaises(ValueError):
            (b1 | b2).get_romskjema_data()

    # ==================================================================
    # populer_kalkulator_data — SKRIVFRI
    # ==================================================================

    def test_populer_kalkulator_data_er_SKRIVFRI(self):
        """🔴 KONTRAKTEN mellom sporene: denne metoden skriver INGENTING.

        Salg eier kalkulatoren; Prosjekt eier oppgavene. Metoden leverer
        kandidat-linjer som overlaget kan skrive — begynner den selv å lage
        `sale.order.line`, får kunden dobbelte linjer i tilbudet så snart
        knappen trykkes to ganger.

        Testen fanger BÅDE at det opprettes tilbudslinjer og at befaringens
        egen tilstand endres (status, felt, rom).
        """
        lead = self._lag_lead()
        bef = self.Befaring.browse(self.Befaring.opprett_fra_lead(lead.id))
        self._lag_rom(bef, name="Stue", tiltak="Male vegger", areal=20.0)

        SOL = self.env["sale.order.line"]
        antall_linjer_for = SOL.search_count([])
        antall_bef_for = self.Befaring.search_count([])
        antall_rom_for = self.Rom.search_count([])
        state_for = bef.state
        so_for = bef.sale_order_id

        linjer = bef.populer_kalkulator_data()

        self.assertTrue(linjer, "Metoden skal returnere kandidat-linjer")
        self.assertEqual(
            SOL.search_count([]), antall_linjer_for,
            "populer_kalkulator_data OPPRETTET tilbudslinjer — den skal være skrivfri",
        )
        self.assertEqual(self.Rom.search_count([]), antall_rom_for,
                         "Metoden opprettet/slettet rom")
        self.assertEqual(self.Befaring.search_count([]), antall_bef_for,
                         "Metoden opprettet befaringer")
        self.assertEqual(bef.state, state_for,
                         "Metoden endret status — den skal ikke røre tilstanden")
        self.assertEqual(bef.sale_order_id, so_for,
                         "Metoden koblet et tilbud på egen hånd")

    def test_populer_kalkulator_data_kan_kalles_flere_ganger(self):
        """Idempotent: to kall gir samme svar, ikke doble linjer.

        Direkte konsekvens av at metoden er skrivfri — men det er nettopp
        denne oppførselen bransjelaget lener seg på når befareren trykker
        «Fyll tilbud» to ganger på en treg mobil.
        """
        bef = self._lag_befaring()
        self._lag_rom(bef, name="Stue", tiltak="Male vegger")
        forste = bef.populer_kalkulator_data()
        andre = bef.populer_kalkulator_data()
        self.assertEqual(forste, andre, "Gjentatt kall ga ulikt resultat")

    def test_populer_kalkulator_data_hopper_over_rom_uten_tiltak(self):
        """Et rom uten tiltak har ingenting å prise — ingen tom tilbudslinje.

        En linje uten tekst i et tilbud er verre enn ingen linje: kunden ser
        en post han ikke forstår, og selgeren må forklare den.
        """
        bef = self._lag_befaring()
        self._lag_rom(bef, name="Med tiltak", tiltak="Male")
        self._lag_rom(bef, name="Uten tiltak")
        linjer = bef.populer_kalkulator_data()
        self.assertEqual(len(linjer), 1)
        self.assertEqual(linjer[0]["post"], "Med tiltak")

    def test_populer_kalkulator_data_foretrekker_ai_tiltak(self):
        """AI-teksten er den strukturerte — den slår fritekst når begge finnes."""
        bef = self._lag_befaring()
        self._lag_rom(bef, name="Bad", tiltak="fritekst",
                      ai_tiltak_no="Rive og flislegge bad")
        linjer = bef.populer_kalkulator_data()
        self.assertEqual(linjer[0]["beskrivelse"], "Rive og flislegge bad")

    def test_populer_kalkulator_data_bruker_fritekst_naar_ai_mangler(self):
        """Uten AI-tekst faller vi tilbake på befarerens egne ord.

        Fangsten skal aldri gå tapt fordi AI-strukturering ikke er kjørt.
        """
        bef = self._lag_befaring()
        self._lag_rom(bef, name="Bod", tiltak="Rydde og male")
        self.assertEqual(
            bef.populer_kalkulator_data()[0]["beskrivelse"], "Rydde og male")

    def test_populer_kalkulator_data_etikett_med_etasje(self):
        """Posten må skille «Bad (1)» fra «Bad (2)» i et bygg med flere etasjer.

        Uten etasjen i etiketten står det to identiske «Bad»-poster i tilbudet,
        og ingen vet hvilken som er priset hva.
        """
        bef = self._lag_befaring()
        self._lag_rom(bef, name="Bad", etasje="2", tiltak="Male", sequence=10)
        self._lag_rom(bef, name="Bod", tiltak="Male", sequence=20)
        linjer = bef.populer_kalkulator_data()
        self.assertEqual(linjer[0]["post"], "Bad (2)")
        self.assertEqual(linjer[1]["post"], "Bod",
                         "Uten etasje skal etiketten være romnavnet alene")

    def test_populer_kalkulator_data_baerer_rom_id_og_areal(self):
        """Overlaget må kunne spore linja tilbake til rommet og regne på areal."""
        bef = self._lag_befaring()
        rom = self._lag_rom(bef, name="Stue", tiltak="Male", areal=24.5)
        linje = bef.populer_kalkulator_data()[0]
        self.assertEqual(linje["rom_id"], rom.id)
        self.assertEqual(linje["areal"], 24.5)

    def test_populer_kalkulator_data_tom_befaring_gir_tom_liste(self):
        """🔑 RANDTILFELLE: ingen rom = ingen linjer, ikke krasj."""
        self.assertEqual(self._lag_befaring().populer_kalkulator_data(), [])

    # ==================================================================
    # TILSTANDSKJEDEN utkast → pagaar → fullfort → overfort
    # ==================================================================

    def test_action_start_flytter_utkast_til_pagaar(self):
        bef = self._lag_befaring()
        self.assertEqual(bef.state, "utkast", "Ny befaring skal starte i utkast")
        bef.action_start()
        self.assertEqual(bef.state, "pagaar")

    def test_action_start_rorer_ikke_paagaaende_befaring(self):
        """🔑 Knappen skal ikke kunne kaste en befaring TILBAKE.

        `action_start` setter kun `pagaar` fra `utkast`. Ble den kjørt på en
        fullført befaring, ville arbeidet sett uferdig ut igjen — og Prosjekt
        ville mistet signalet om at Salg er ferdig.
        """
        bef = self._lag_befaring(state="fullfort")
        bef.action_start()
        self.assertEqual(bef.state, "fullfort",
                         "action_start rullet en fullført befaring tilbake")

    def test_action_fullfor_setter_fullfort(self):
        bef = self._lag_befaring(state="pagaar")
        bef.action_fullfor()
        self.assertEqual(bef.state, "fullfort")

    def test_hele_kjeden_i_rekkefolge(self):
        """🔴 KONTRAKTEN: utkast → pagaar → fullfort → overfort.

        Skillelinjen mellom sporene ligger PÅ `overfort`: alt før eies av
        Salg, alt etter av Prosjekt. Endrer noen rekkefølgen, flytter de
        eierskapet uten å vite det.
        """
        lead = self._lag_lead()
        bef = self._lag_befaring(lead_id=lead.id)
        self.assertEqual(bef.state, "utkast")

        bef.action_start()
        self.assertEqual(bef.state, "pagaar")

        bef.action_fullfor()
        self.assertEqual(bef.state, "fullfort")

        bef.project_id = self._lag_prosjekt()
        bef.action_overfor()
        self.assertEqual(bef.state, "overfort")

    def test_action_start_virker_paa_flere_befaringer(self):
        """Knappene er skrevet for recordset — massevalg skal virke.

        Metodene løkker over `self`; testen låser at ingen legger inn en
        `ensure_one()` som ville brutt massehandling fra listevisningen.
        """
        b1 = self._lag_befaring()
        b2 = self._lag_befaring(name="TEST Befaring 2")
        (b1 | b2).action_start()
        self.assertEqual(b1.state, "pagaar")
        self.assertEqual(b2.state, "pagaar")

    # ==================================================================
    # overfor_til_prosjekt — broen ut til prosjektsporet
    # ==================================================================

    def test_overfor_til_prosjekt_uten_prosjekt_gir_False(self):
        """🔴 Uten prosjekt: False, og INGEN tilstandsendring.

        Dette er selve sperren mellom sporene. Ble status satt til `overfort`
        uten at et prosjekt fantes, ville Salg sluppet befaringen og Prosjekt
        aldri fått den — den forsvinner mellom to stoler.
        """
        bef = self._lag_befaring(state="fullfort")
        self.assertFalse(bef.project_id, "Forutsetningen: intet prosjekt satt")

        res = bef.overfor_til_prosjekt()

        self.assertIs(res, False, "Uten prosjekt skal metoden gi False")
        self.assertEqual(
            bef.state, "fullfort",
            "Status ble flyttet til «%s» uten at et prosjekt fantes" % bef.state,
        )
        self.assertFalse(bef.befaring_task_id,
                         "Det ble laget en oppgave uten prosjekt")

    def test_overfor_til_prosjekt_oppretter_oppgaven_Befaring(self):
        """Ankeret i prosjektet: oppgaven «Befaring» opprettes om den mangler."""
        prosjekt = self._lag_prosjekt()
        bef = self._lag_befaring(state="fullfort", project_id=prosjekt.id)

        task_id = bef.overfor_til_prosjekt()

        self.assertTrue(task_id, "Ingen oppgave-id returnert")
        task = self.Task.browse(task_id)
        self.assertTrue(task.exists())
        self.assertEqual(task.project_id, prosjekt)
        self.assertEqual(bef.befaring_task_id, task)
        self.assertEqual(bef.state, "overfort")
        self.assertEqual(task.company_id, bef.company_id,
                         "Oppgaven skal arve befaringens firma")

    def test_overfor_til_prosjekt_gjenbruker_eksisterende_oppgave(self):
        """🔑 To befaringer på samme prosjekt skal dele oppgaven «Befaring».

        Uten gjenbruk får prosjektet «Befaring», «Befaring», «Befaring» — og
        dokumentene spres på tre oppgaver ingen finner igjen.
        """
        prosjekt = self._lag_prosjekt()
        eksisterende = self.Task.create({
            "name": "Befaring", "project_id": prosjekt.id,
            "company_id": self.company.id,
        })
        bef = self._lag_befaring(state="fullfort", project_id=prosjekt.id)

        task_id = bef.overfor_til_prosjekt()

        self.assertEqual(
            task_id, eksisterende.id,
            "Det ble laget en NY «Befaring»-oppgave selv om en fantes",
        )
        self.assertEqual(
            self.Task.search_count([
                ("project_id", "=", prosjekt.id), ("name", "=", "Befaring"),
            ]), 1, "Prosjektet fikk dublett-oppgaver",
        )

    def test_overfor_til_prosjekt_er_idempotent(self):
        """To trykk på knappen skal ikke gi to oppgaver.

        Mobilflaten mister nett midt i overføringen; befareren trykker igjen.
        Da må andre kall lande på samme oppgave.
        """
        prosjekt = self._lag_prosjekt()
        bef = self._lag_befaring(state="fullfort", project_id=prosjekt.id)

        forste = bef.overfor_til_prosjekt()
        andre = bef.overfor_til_prosjekt()

        self.assertEqual(forste, andre, "Andre kall ga en annen oppgave")
        self.assertEqual(
            self.Task.search_count([
                ("project_id", "=", prosjekt.id), ("name", "=", "Befaring"),
            ]), 1, "Gjentatt overføring laget dublett",
        )

    def test_overfor_til_prosjekt_bytter_oppgave_naar_prosjektet_byttes(self):
        """🔑 Flyttes befaringen til et annet prosjekt, skal ankeret følge med.

        `befaring_task_id` pekte på oppgaven i det GAMLE prosjektet. Uten
        sjekken `task.project_id != self.project_id` ville dokumentene blitt
        liggende igjen i prosjektet befaringen ikke lenger hører til.
        """
        prosjekt_a = self._lag_prosjekt(name="TEST Prosjekt A")
        prosjekt_b = self._lag_prosjekt(name="TEST Prosjekt B")
        bef = self._lag_befaring(state="fullfort", project_id=prosjekt_a.id)

        task_a = self.Task.browse(bef.overfor_til_prosjekt())
        bef.project_id = prosjekt_b
        task_b = self.Task.browse(bef.overfor_til_prosjekt())

        self.assertNotEqual(task_a, task_b,
                            "Ankeret ble hengende i det gamle prosjektet")
        self.assertEqual(task_b.project_id, prosjekt_b)
        self.assertEqual(bef.befaring_task_id, task_b)

    def test_action_overfor_kaller_overforingen(self):
        """UI-knappen og API-metoden skal gjøre det samme."""
        prosjekt = self._lag_prosjekt()
        bef = self._lag_befaring(state="fullfort", project_id=prosjekt.id)
        bef.action_overfor()
        self.assertEqual(bef.state, "overfort")
        self.assertTrue(bef.befaring_task_id)

    def test_overfor_til_prosjekt_krever_en_befaring(self):
        """`ensure_one()` — massevalg her ville koblet flere befaringer feil."""
        prosjekt = self._lag_prosjekt()
        b1 = self._lag_befaring(project_id=prosjekt.id)
        b2 = self._lag_befaring(name="TEST Befaring 2", project_id=prosjekt.id)
        with self.assertRaises(ValueError):
            (b1 | b2).overfor_til_prosjekt()

    # ==================================================================
    # HELE BROEN: lead → rom/funn → romskjema → prosjekt
    # ==================================================================

    def test_hele_broen_fra_salgsmulighet_til_prosjektoppgave(self):
        """🔑 Integrasjon: den veien en ekte befaring faktisk går.

        Enkelttestene over kan alle være grønne mens broen likevel er brutt i
        et skjøt. Denne bygger hele tilstanden selv og følger den fra
        salgsmulighet til oppgaven i prosjektet.
        """
        lead = self._lag_lead(name="TEST Rehab Kabelgata 12")
        bef = self.Befaring.browse(self.Befaring.opprett_fra_lead(lead.id))

        stue = self._lag_rom(bef, name="Stue", etasje="1", areal=30.0,
                             ai_tiltak_no="Male vegger og tak", sequence=10)
        self._lag_rom(bef, name="Bad", etasje="2", areal=6.0,
                      tiltak="Rive og flislegge", sequence=20)
        self.Funn.create({
            "befaring_id": bef.id, "rom_id": stue.id,
            "name": "Sprekk i vegg", "type": "avvik", "alvorlighet": "middels",
        })

        # Salgsfasen
        bef.invalidate_recordset(["rom_antall", "funn_antall"])
        self.assertEqual(bef.rom_antall, 2)
        self.assertEqual(bef.funn_antall, 1)
        self.assertEqual(len(bef.populer_kalkulator_data()), 2)
        self.assertEqual(len(bef.get_romskjema_data()["rom"]), 2)

        # Overgangen til prosjektsporet
        bef.action_fullfor()
        self.assertEqual(bef.state, "fullfort")
        self.assertIs(bef.overfor_til_prosjekt(), False,
                      "Uten prosjekt skal broen være stengt")

        bef.project_id = self._lag_prosjekt(name="TEST Kabelgata 12")
        task = self.Task.browse(bef.overfor_til_prosjekt())
        self.assertEqual(bef.state, "overfort")
        self.assertEqual(task.project_id, bef.project_id)
        self.assertEqual(bef.company_id, lead.company_id,
                         "Firmaet skal ha fulgt hele veien fra salgsmuligheten")

    # ==================================================================
    # DOKUMENTERT MANGEL — ikke fikset her (Salg eier feltet)
    # ==================================================================

    def test_rom_mangler_tilstandsfelt_dokumentert(self):
        """📌 DOKUMENTERT MANGEL, ikke en feil å fikse her.

        Fasiten krever et tilstandsfelt «God / Slitt / Må rives» på
        `fiq.befaring.rom`. Det finnes IKKE i dag. Feltet eies av SALGS-sporet
        (det er en vurdering befareren gjør før tilbudet), så det legges ikke
        til herfra.

        Testen står som en LEVENDE notis: den passerer i dag ved å slå fast
        fravaeret, og skal snus til en ekte test den dagen Salg legger feltet
        inn. Uten den ville mangelen bare vaert en setning i en rapport ingen
        leser.
        """
        self.assertNotIn(
            "tilstand", self.Rom._fields,
            "Tilstandsfeltet «God/Slitt/Må rives» er nå lagt til av Salg — "
            "snu denne testen til en ekte test av verdiene og fjern notisen.",
        )
