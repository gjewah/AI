# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.modules.module import get_manifest


# Runs after ALL modules are loaded, not during fiq_gui_control's own install.
#
# Why this matters: other installed modules (sale_timesheet, purchase_stock) add
# NOT NULL columns to project.project and res.partner. Those constraints live in
# the database, but their defaults are applied by Odoo in Python. During at_install
# the registry only holds this module's depends (web, project), so those fields are
# unknown, no default is applied, and the INSERT omits the column -> NotNullViolation.
# post_install gives the full registry, matching how the code actually runs.
@tagged("-at_install", "post_install")
class TestFiqControlRoom(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Config = self.env["fiq.gui.control.config"]
        self.action = self.env.ref("fiq_gui_control.action_fiq_gui_control")

    def test_groups_exist_and_hierarchy(self):
        gu = self.env.ref("fiq_gui_control.group_user")
        gm = self.env.ref("fiq_gui_control.group_manager")
        ga = self.env.ref("fiq_gui_control.group_admin")
        self.assertTrue(gu and gm and ga)
        # Leder arver Bruker; Admin arver Leder
        self.assertIn(gu, gm.implied_ids)
        self.assertIn(gm, ga.implied_ids)
        # Alle interne brukere (base.group_user) får Hovedmeny-Bruker
        self.assertIn(gu, self.env.ref("base.group_user").implied_ids)

    def test_get_my_config_creates_and_returns(self):
        cfg = self.Config.get_my_config()
        for key in ("show", "level", "is_admin", "company_name", "accent", "company_id", "companies"):
            self.assertIn(key, cfg)
        self.assertEqual(set(cfg["show"].keys()),
                         {"kpis", "projects", "kommunikasjon", "activity", "tasks", "chart", "copilot", "quick"})
        self.assertTrue(self.Config.search([("user_id", "=", self.env.uid)]))

    def test_set_widget_persists(self):
        self.Config.get_my_config()
        self.Config.set_widget("kpis", False)
        rec = self.Config.search(
            [("user_id", "=", self.env.uid), ("company_id", "=", self.env.company.id)], limit=1)
        self.assertFalse(rec.show_kpis)
        self.Config.set_widget("kpis", True)
        self.assertTrue(rec.show_kpis)

    def test_unique_per_user_company(self):
        self.Config.get_my_config()
        # andre kall gir samme record (ikke duplikat)
        n = self.Config.search_count(
            [("user_id", "=", self.env.uid), ("company_id", "=", self.env.company.id)])
        self.Config.get_my_config()
        self.assertEqual(
            self.Config.search_count(
                [("user_id", "=", self.env.uid), ("company_id", "=", self.env.company.id)]), n)

    def test_record_rule_isolation(self):
        userA = new_test_user(self.env, login="hm_a", groups="fiq_gui_control.group_user")
        userB = new_test_user(self.env, login="hm_b", groups="fiq_gui_control.group_user")
        self.Config.with_user(userA).get_my_config()
        # B skal ikke se A sitt oppsett
        seen_by_b = self.Config.with_user(userB).search([])
        self.assertFalse(seen_by_b.filtered(lambda c: c.user_id == userA))

    def test_get_kommunikasjon_shape_and_direction(self):
        # Logg en melding på et prosjekt → skal dukke opp med retning + avsender
        proj = self.env["project.project"].create({"name": "HM Komm Test"})
        proj.message_post(body="Hei", message_type="comment")
        rows = self.Config.get_kommunikasjon("alle", 50)
        self.assertIsInstance(rows, list)
        if rows:
            r = rows[0]
            for key in ("id", "kind", "author", "author_id", "direction",
                        "subject", "date", "model", "res_id", "element"):
                self.assertIn(key, r)
            self.assertIn(r["direction"], ("sendt", "mottatt"))

    def test_get_dashboards_only_existing_xmlids(self):
        rows = self.Config.get_dashboards()
        self.assertIsInstance(rows, list)
        for r in rows:
            self.assertIn("xmlid", r)
            self.assertIn("label", r)
            # Hver returnert xmlid MÅ faktisk resolve (env.ref-guard)
            self.assertTrue(self.env.ref(r["xmlid"], raise_if_not_found=False))

    def test_company_branding_fields(self):
        for f in ("fiq_control_accent", "fiq_control_logo", "fiq_control_as_home"):
            self.assertIn(f, self.env.company._fields)

    def test_set_home_admin_controlled(self):
        u = new_test_user(self.env, login="hm_home", groups="fiq_gui_control.group_user")
        self.assertEqual(u.company_id, self.env.company)
        # Flag AV → lås opp (ingen påtvunget home)
        self.env.company.fiq_control_as_home = False
        self.Config._action_set_home_all()
        # Flag PÅ → home settes til Hovedmeny for interne brukere i firmaet
        self.env.company.fiq_control_as_home = True
        self.Config._action_set_home_all()
        u.invalidate_recordset(["action_id"])
        self.assertEqual(u.action_id.id, self.action.id)

    def test_gui_build_matcher_manifest(self):
        """GUI_BUILD i control_room.js MÅ være lik "version" i manifestet.

        🔴 GJERMUND FANGET DETTE 20.07.2026 — og han hadde meldt samme feil TRE ganger før:
        «det røde båndet kommer når det er noe feil med push på GIT eller noen av modulene
        har meldt til feil bygg».

        Han har rett. Banneret «A new version is installed» er IKKE en beskjed om at
        nettleseren har gammel cache — det er en EKTE feilmelding om at leveransen er
        inkonsistent. Jeg feiltolket det som et cache-problem og ba ham laste på nytt.

        MEKANIKKEN: `control_room.js` sammenligner den hardkodede GUI_BUILD mot installert
        modulversjon (`get_my_config` → `version_installed`). Er de ulike, vises banneret —
        og det forsvinner ALDRI, uansett hvor mange ganger man laster siden på nytt.

        HVORFOR DET SKJEDDE: manifestet ble bumpet fem ganger på én dag (6.94 → 7.0.0) mens
        GUI_BUILD sto igjen på 6.93. Kommentaren over konstanten advarer eksplisitt mot
        nøyaktig dette — den ble ikke lest.

        Denne testen gjør at det ikke kan gjenta seg: glemmer noen å bumpe GUI_BUILD,
        feiler testen FØR push i stedet for at Gjermund oppdager et rødt banner i Odoo.
        """
        import re
        # Odoo 19: `tools.file_path` — `get_module_resource` finnes IKKE lenger.
        # Verifisert i kilden (odoo/tools/misc.py:196) før bruk, ikke antatt fra hukommelsen.
        from odoo.tools import file_path
        sti = file_path("fiq_gui_control/static/src/control_room.js")
        with open(sti, "r", encoding="utf-8") as f:
            js = f.read()
        m = re.search(r'const\s+GUI_BUILD\s*=\s*"([^"]+)"', js)
        self.assertTrue(m, "GUI_BUILD mangler i control_room.js")
        manifest = get_manifest("fiq_gui_control").get("version", "")
        self.assertEqual(
            m.group(1), manifest,
            "GUI_BUILD (%s) != manifest (%s). Bump BEGGE i SAMME commit — ellers viser "
            "Kontrollrommet «A new version is installed»-banneret som aldri forsvinner, "
            "og Gjermund ser en leveranse som ser ødelagt ut." % (m.group(1), manifest),
        )

    def test_nokkel_alias_dekker_menyens_faste_noekler(self):
        """Hver fast menynøkkel MÅ finne flatens komponent — direkte eller via alias.

        🔴 FUNNET AV AI PK 23.07.2026. Menyen og flatene brukte ULIKE navn for SAMME flate:
            meny «gui_prj»  ↔  flaten registrerte «prj»
            meny «gui_fin»  ↔  «finans»    ·  «gui_rgs» ↔ «regnskap»
            meny «kommunikasjon» ↔ «komm»  ·  «airmm»   ↔ «ai_kr»
        `registry.get()` slår opp EKSAKT → ingen av dem ble funnet. `runAction` falt til
        `doAction`, og RAMMEN FORSVANT. Prosjekt meldte symptomet; dette var årsaken.

        🛑 Dedup-koden fra v6.92 SKJULTE det: den fjernet dubletter fra menyen, men sa
        ingenting om hvorvidt oppføringen pekte på noe som finnes. «Ingen dubletter» ble
        lest som «alt stemmer» — i fire dager.

        Testen leser BEGGE lister fra kildekoden og krever at hver fast nøkkel som har en
        registrert motpart, faktisk finner den. Legger noen til et menypunkt uten alias,
        feiler dette FØR push i stedet for at rammen forsvinner hos Gjermund.
        """
        import re
        from odoo.tools import file_path
        with open(file_path("fiq_gui_control/static/src/control_room.js"),
                  "r", encoding="utf-8") as f:
            js = f.read()

        # De faste menynøklene (navItems)
        faste = set(re.findall(r'key:\s*"([a-z_]+)"', js))
        # Aliastabellen
        blokk = re.search(r"NOKKEL_ALIAS\s*=\s*\{(.*?)\}", js, re.S)
        self.assertTrue(blokk, "NOKKEL_ALIAS mangler — nøkkelsplittelsen er ikke håndtert")
        alias = dict(re.findall(r"(\w+):\s*\"([a-z_]+)\"", blokk.group(1)))

        # Nøkler vi VET flatene registrerer under et annet navn (målt 23.07).
        kjent_splittelse = {
            "kommunikasjon": "komm",
            "gui_rgs": "regnskap",
            "gui_fin": "finans",
            "gui_prj": "prj",
            "airmm": "ai_kr",
        }
        for menynokkel, flatenokkel in kjent_splittelse.items():
            self.assertIn(
                menynokkel, faste,
                "menynøkkelen «%s» er borte fra navItems — er den omdøpt, må aliaset "
                "oppdateres i samme commit" % menynokkel,
            )
            self.assertEqual(
                alias.get(menynokkel), flatenokkel,
                "«%s» mangler alias til «%s». Uten det finner runAction ingen komponent, "
                "faller til doAction, og RAMMEN FORSVINNER for brukeren." % (
                    menynokkel, flatenokkel),
            )

    def test_posisjonsdeling_av_som_standard_og_en_bryter(self):
        """Posisjonsdeling er AV som standard, og ÉN bryter dekker begge flater.

        Gjermund 20.07: «egen toggle som slår av GPS for Odoo OG Claude for brukeren
        automatisk, men varsler om det og lar brukeren slå den på om hen bevisst ønsker det.»

        🔑 HVORFOR ÉN BRYTER: gjaldt avslaget bare Odoo, ville brukeren tro hen var usynlig
        mens mobilen fortsatt delte posisjon. Det er den farligste varianten, fordi den ser
        trygg ut. Testen holder standarden AV — en delings-bryter som er på fra start er
        et samtykke ingen har gitt.
        """
        cfg = self.Config.get_my_config()
        self.assertIn("del_posisjon", cfg)
        self.assertFalse(cfg["del_posisjon"], "posisjonsdeling må være AV som standard")

        # Brukerens eget valg skal respekteres begge veier.
        self.Config.sett_posisjonsdeling(True)
        self.assertTrue(self.Config.get_my_config()["del_posisjon"])
        self.Config.sett_posisjonsdeling(False)
        self.assertFalse(self.Config.get_my_config()["del_posisjon"])

    def test_posisjon_slaas_aldri_paa_automatisk(self):
        """🛑 Systemet slår ALDRI posisjonsdeling PÅ av seg selv.

        Ferie kan slå den AV. Ingenting skal slå den PÅ — har brukeren bevisst skrudd den
        på under ferien, skal neste oppslag ikke overstyre det. Automatikk som overkjører
        et menneskelig valg er verre enn ingen automatikk.
        """
        rec = self.Config._get_or_create_current()
        rec.del_posisjon = False
        # Flere oppslag skal ikke endre den fra av til på.
        for _ in range(3):
            self.Config.get_my_config()
        rec.invalidate_recordset(["del_posisjon"])
        self.assertFalse(rec.del_posisjon,
                         "posisjonsdeling ble slått PÅ av systemet — det skal aldri skje")

    def test_responsiv_ramme_har_mobilhaandtering(self):
        """Rammen må fungere på mobil (Gjermund 23.07).

        «Løsningen vet om den er på en mobil eller på en større GUI-flate.»
        Befaringen blir ÉN responsiv flate, ikke en PC/mobil-velger — da må rammen
        under den også virke på liten skjerm.

        🔑 Vi måler BREDDE, ikke enhetstype: en telefon i landskap og et smalt vindu på
        PC har samme problem. Enhetsgjetting bommer på begge.

        Testen holder tre ting i live: menyknappen finnes, menyen kan foldes bort, og
        berøringsmålene er store nok. Alle tre er lette å miste ved en opprydding —
        og feilen ville først vist seg på en telefon, der ingen av oss tester daglig.
        """
        from odoo.tools import file_path
        with open(file_path("fiq_gui_control/static/src/control_room.scss"),
                  "r", encoding="utf-8") as f:
            scss = f.read()
        with open(file_path("fiq_gui_control/static/src/control_room.xml"),
                  "r", encoding="utf-8") as f:
            xml = f.read()

        self.assertIn("fiq_hm_menyknapp", xml, "menyknappen mangler i malen")
        self.assertIn("fiq_hm_menyknapp", scss, "menyknappen mangler stil")
        self.assertRegex(
            scss, r"@media\s*\(max-width:\s*760px\)",
            "ingen bruddpunkt for liten skjerm",
        )
        self.assertIn("min-height: 40px", scss,
                      "berøringsmål under 40px — en finger treffer ikke en 20px-knapp")

    # ── INNBOKSEN: nøyaktig to kilder ─────────────────────────────────────────────────

    def test_innboksen_peker_aldri_ut_av_kontrollrommet(self):
        """Innboksens punkter skal peke på FIQ-flater — aldri på Odoos egne lister.

        🔴 Gjermund 23.07, to ganger på én kveld: først «du har koblet tasks til odoo native og
        det er eneste menyen som virker og den skal ikke en gang være der», så «tasks og
        aktiviteter skal ikke ligge der».

        🔑 Feilen var ikke feil handling, men feil RETNING. `project.action_view_task` og
        `mail.mail_activity_action` er alltid installert, så de to punktene var de eneste som
        åpnet noe — mens de to ekte kildene sto ukoblet. **De fungerende punktene var
        kamuflasjen**: de fikk innboksen til å se halvferdig ut i stedet for ukoblet, og det er
        forskjellen på et problem som blir meldt og ett som blir trodd.

        Testen låser at ingen legger dem inn igjen «fordi de finnes fra før» — det er nettopp
        derfor nøklene ble fjernet helt, ikke bare menypunktene.
        """
        handlinger = self.Config.get_actions()
        for nokkel in ("oppgaver", "aktiviteter"):
            self.assertNotIn(
                nokkel, handlinger,
                "«%s» er tilbake i innboksens oppslagstabell — den peker ut av "
                "Kontrollrommet og skal ikke finnes" % nokkel,
            )
        # De to som SKAL være der. At de er ukoblet i en base er PORT 0 (modulen ikke
        # installert), ikke en kodefeil — men nøkkelen skal alltid finnes i tabellen.
        for nokkel in ("epost", "ai"):
            self.assertIn(
                nokkel, handlinger,
                "innboksens kilde «%s» mangler i oppslagstabellen" % nokkel,
            )

    def test_innboksen_har_noeyaktig_to_kilder(self):
        """Nøyaktig to punkter i innboksen: 0.1 E-post og 0.2 AI-meldinger.

        Testen leser malen/koden framfor å telle i et kjørende grensesnitt, fordi antallet er
        en BESTILLING og ikke en tilfeldighet. Vokser lista igjen, skal det være et bevisst
        valg noen må endre denne testen for å gjøre.
        """
        import re
        from odoo.tools import file_path
        with open(file_path("fiq_gui_control/static/src/control_room.js"),
                  "r", encoding="utf-8") as f:
            js = f.read()
        blokk = re.search(r"get innboksKilder\(\)\s*\{(.*?)\n    \}", js, re.S)
        self.assertTrue(blokk, "fant ikke innboksKilder")
        kilder = re.findall(r'nr:\s*"(0\.\d)"', blokk.group(1))
        self.assertEqual(
            kilder, ["0.1", "0.2"],
            "innboksen skal ha nøyaktig to kilder (E-post, AI-meldinger), fant: %s" % kilder,
        )

    # ── AVDELING-raden (utkast 08) ────────────────────────────────────────────────────

    def test_avdelinger_svarer_uten_aa_krasje(self):
        """Avdelingsraden skal ALDRI felle forsiden — uansett om personalmodulen finnes.

        🔑 Dette er hele poenget med testen: `hr` står IKKE i modulens `depends` (kun `web`
        og `project`), og skal ikke gjøre det — Kontrollrommet må virke i en base uten
        personalmodulen. Metoden må derfor svare en LISTE i begge tilfeller: med HR gir den
        avdelingene, uten HR gir den tom liste, og malen skjuler raden.

        🛑 En `except` som svarer `None` i stedet for `[]` ville gitt en tom rad med bare
        etiketten «AVDELING» stående — et filter uten valg. Testen låser returtypen.
        """
        ut = self.Config.get_avdelinger()
        self.assertIsInstance(
            ut, list,
            "get_avdelinger må returnere en liste også når personalmodulen mangler",
        )
        for rad in ut:
            self.assertIn("id", rad)
            self.assertIn("name", rad)

    def test_avdelinger_er_firma_scopet(self):
        """Raden skal speile firmaet du står i — ikke vise alle firmaers avdelinger.

        Samme feil som `get_areas()` hadde før 7.2.0: den hentet alle toppnivå-prosjekter
        og ga 17 treff der bare ett var en ekte firma-rot. Sendes en firma-id inn, skal
        svaret aldri inneholde en avdeling som tilhører et ANNET firma.
        """
        if self.env.get("hr.department") is None:
            self.skipTest("personalmodulen er ikke installert i denne basen")
        firma = self.env.company
        for rad in self.Config.get_avdelinger(company_id=firma.id):
            dep = self.env["hr.department"].sudo().browse(rad["id"])
            self.assertIn(
                dep.company_id.id, (False, firma.id),
                "avdeling fra et annet firma lekket inn i raden",
            )

    def test_avdelingsraden_skjules_naar_tom(self):
        """Malen må skjule HELE båndet når det ikke finnes avdelinger.

        Uten `t-if` ville en base uten personalmodulen vist et tomt filterbånd med bare
        ordet «AVDELING» — det ser ut som noe som er i stykker, ikke som noe som ikke
        gjelder. **Ingen tom rad, ingen feilmelding.**
        Berøringsmålet er med her fordi avdelingsknappene er de minste på flaten.
        """
        from odoo.tools import file_path
        with open(file_path("fiq_gui_control/static/src/control_room.xml"),
                  "r", encoding="utf-8") as f:
            xml = f.read()
        with open(file_path("fiq_gui_control/static/src/control_room.scss"),
                  "r", encoding="utf-8") as f:
            scss = f.read()
        self.assertIn(
            't-if="state.avdelinger.length"', xml,
            "avdelingsbåndet mangler t-if — det ville stått tomt uten personalmodulen",
        )
        self.assertIn("fiq_hm_avdrad", scss, "avdelingsbåndet mangler stil")
        self.assertRegex(
            scss, r"\.fiq_hm_nav,[^\n]*\.fiq_hm_avd,",
            "fiq_hm_avd mangler i 40px-regelen — de minste knappene på flaten",
        )

    # ── TIDSLINJEN (utkast 08) ────────────────────────────────────────────────────────

    def test_tidslinje_har_seks_faste_fargetrinn(self):
        """Skalaen skal ha ALLE seks trinn, og de skal være ulike farger.

        🔑 Hvorfor en test på dette: skalaen sto i den godkjente spesifikasjonen fra 20.07
        og ble aldri bygget — den var «spesifisert» i fire dager uten at noen målte at den
        manglet. En regel som bare finnes i et dokument, finnes ikke.

        🛑 Seks IDENTISKE verdier ville bestått en ren «finnes trinnene?»-sjekk, men gitt
        en tidslinje der alt ser like travelt ut. Derfor sjekkes også at de er forskjellige.
        """
        from odoo.tools import file_path
        with open(file_path("fiq_gui_control/static/src/control_room.scss"),
                  "r", encoding="utf-8") as f:
            scss = f.read()
        import re
        farger = {}
        for trinn in ("t0", "t20", "t40", "t60", "t80", "t100"):
            treff = re.search(r"--%s:\s*(#[0-9a-fA-F]{3,8})" % trinn, scss)
            self.assertTrue(treff, "travelhetstrinn --%s mangler i stilarket" % trinn)
            farger[trinn] = treff.group(1).lower()
        self.assertEqual(
            len(set(farger.values())), 6,
            "to travelhetstrinn har SAMME farge — da kan de ikke skilles: %s" % farger,
        )

    def test_tidslinjen_viser_aldri_aar(self):
        """«Aldri år» er et krav fra Gjermund i grunnstruktur-specen §2.5: 52 ruter sier
        ingenting. Bare uke og måned skal kunne velges.

        Testen finnes fordi det er akkurat den slags krav som forsvinner stille når noen
        senere «utvider» en velger i beste mening.
        """
        from odoo.tools import file_path
        with open(file_path("fiq_gui_control/static/src/control_room.js"),
                  "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn('tlMode: "uke"', js, "tidslinjen mangler standardvisning")
        self.assertNotRegex(
            js, r'setTlMode\(["\']aar["\']\)',
            "tidslinjen har fått årsvisning — spec §2.5 forbyr den",
        )

    def test_tidslinjens_valg_overlever_tur_til_odoo(self):
        """Avdeling og uke/måned er BRUKERVALG og må ligge i fryselista.

        Utelates de, nullstilles de stille når man kommer tilbake fra native Odoo — og det
        leses som at flaten glemte valget, ikke som at det aldri ble lagret.
        🛑 Selve avdelings-LISTA skal derimot IKKE fryses: den hentes fra serveren hver gang.
        Fryses data i stedet for valg, viser flaten gamle avdelinger etter en endring.
        """
        from odoo.tools import file_path
        with open(file_path("fiq_gui_control/static/src/control_room.js"),
                  "r", encoding="utf-8") as f:
            js = f.read()
        import re
        blokk = re.search(r"FREEZE_KEYS\s*=\s*\[(.*?)\]", js, re.S)
        self.assertTrue(blokk, "fant ikke FREEZE_KEYS")
        nokler = blokk.group(1)
        self.assertIn('"avdelingId"', nokler, "avdelingsvalget fryses ikke")
        self.assertIn('"tlMode"', nokler, "tidslinjens uke/måned fryses ikke")
        self.assertNotIn('"avdelinger"', nokler,
                         "selve avdelingslista skal IKKE fryses — kun valget")
