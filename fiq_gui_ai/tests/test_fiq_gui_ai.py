"""Tester for FIQ AI co-worker-flaten (`fiq.gui.ai.assistent`).

HVA MODULEN GJØR: to tjenester bak co-worker-flaten —
  * `spor(melding, kontekst)` → spør Claude via Anthropics Messages API og
    returnerer ren tekst. Egen `requests.post`, uavhengig av `fiq_ai`-veien.
  * `get_tilstedevaerelse()` → hvem av de interne brukerne som er pålogget.

HVORFOR TESTENE FINNES:
  * 🔴 `spor()` har en KONTRAKT: den skal ALDRI kaste. Kaster den, dør hele
    co-worker-panelet i grensesnittet — ikke bare AI-svaret. Feilstien ER
    funksjonaliteten her, og den er den som sjelden testes.
  * API-NØKKELEN leses fra ir.config_parameter og settes i `x-api-key`. Lekker
    den til logg, retur eller feilmelding, er den kompromittert.
  * Tilstedeværelse leser res.users. Kjøres den ikke som innlogget bruker,
    kan den lekke brukere på tvers av firma.

🛑 INGEN NETTVERK: `spor()` gjør et EKSTERNT HTTP-kall. HVERT eneste kall i disse
testene mocker `requests.post` i modulens eget navnerom
(`odoo.addons.fiq_gui_ai.models.fiq_gui_ai_assistent.requests.post`). En test som
ringer ut på nettet er ikke en test — den er en produksjonshendelse.

PORT 6-disiplin: hver test OPPRETTER sin egen tilstand (systemparametere,
brukere, mocket svar). Ingen test leser bare det basen tilfeldigvis har.
"""

from unittest.mock import MagicMock, patch

import requests

from odoo.addons.fiq_gui_ai.models.fiq_gui_ai_assistent import (
    ANTHROPIC_URL,
    ANTHROPIC_VERSION,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    PARAM_KEY,
    PARAM_MODEL,
    REQUEST_TIMEOUT,
)
from odoo.tests import TransactionCase, tagged

MOCK_POST = "odoo.addons.fiq_gui_ai.models.fiq_gui_ai_assistent.requests.post"

TESTNOKKEL = "sk-ant-api03-FIQ-GUI-AI-TESTNOKKEL-abcdefghij"


def _respons(json_data=None, json_exception=None, raise_for_status=None):
    """Bygger et mocket `requests.Response`-objekt — ALDRI et ekte nettverkssvar."""
    resp = MagicMock()
    if raise_for_status is not None:
        resp.raise_for_status.side_effect = raise_for_status
    else:
        resp.raise_for_status.return_value = None
    if json_exception is not None:
        resp.json.side_effect = json_exception
    else:
        resp.json.return_value = json_data
    return resp


def _tekstsvar(tekst="Hei, jeg er co-workeren."):
    return _respons(
        {"content": [{"type": "text", "text": tekst}], "stop_reason": "end_turn"}
    )


@tagged("post_install", "-at_install", "fiq_gui_ai")
class TestFiqGuiAiSpor(TransactionCase):
    """`spor()` — kontrakten er: ALDRI kast, alltid gi brukeren noe lesbart."""

    def setUp(self):
        super().setUp()
        self.Assistent = self.env["fiq.gui.ai.assistent"]
        self.icp = self.env["ir.config_parameter"].sudo()
        # OPPRETT vår egen tilstand: kjent nøkkel, ingen overstyrt modell.
        self.icp.set_param(PARAM_KEY, TESTNOKKEL)
        self.icp.set_param(PARAM_MODEL, "")
        self.addCleanup(self.icp.set_param, PARAM_KEY, "")

    # ---------- Modellen ----------

    def test_modellen_er_abstrakt(self):
        """Stateless hjelper — ingen poster å lagre, ingen tabell."""
        self.assertTrue(
            self.Assistent._abstract, "fiq.gui.ai.assistent skal være en AbstractModel"
        )

    # ---------- Tom inndata: ingen kall ut ----------

    def test_tom_melding_ringer_ikke_ut(self):
        """🔴 Et tomt felt skal ALDRI koste et API-kall — og aldri kaste."""
        with patch(MOCK_POST) as mock_post:
            for tomt in ("", "   ", "\n\t", None):
                svar = self.Assistent.spor(tomt)
                self.assertTrue(svar, f"Tom melding {tomt!r} ga tomt svar til brukeren")
                self.assertIsInstance(svar, str)
            mock_post.assert_not_called()

    # ---------- Manglende nøkkel ----------

    def test_uten_noekkel_forklares_det_UTEN_aa_kaste(self):
        """🔴 KONTRAKT: manglende nøkkel er en KONFIGURASJONSFEIL, ikke en krasj.
        Brukeren skal få vite at en administrator må sette parameteren."""
        self.icp.set_param(PARAM_KEY, "")
        with patch(MOCK_POST) as mock_post:
            svar = self.Assistent.spor("Hei")
        mock_post.assert_not_called()
        self.assertIsInstance(svar, str)
        self.assertIn(
            PARAM_KEY, svar, "Brukeren må få vite HVILKEN systemparameter som mangler"
        )

    def test_noekkel_med_bare_mellomrom_teller_som_manglende(self):
        """Et blankt-utseende felt er ikke en nøkkel — vi skal ikke sende 401-kall."""
        self.icp.set_param(PARAM_KEY, "   ")
        with patch(MOCK_POST) as mock_post:
            svar = self.Assistent.spor("Hei")
        mock_post.assert_not_called()
        self.assertIn(PARAM_KEY, svar)

    # ---------- Selve kallet ----------

    def test_kallet_treffer_messages_endepunktet(self):
        """🔴 Anthropic har INGEN /responses. Feil URL = 404 på hvert kall."""
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hva er FIQ?")
        self.assertEqual(mock_post.call_count, 1)
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], ANTHROPIC_URL)
        self.assertEqual(args[0], "https://api.anthropic.com/v1/messages")

    def test_headerne_foelger_anthropic_kontrakten(self):
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(headers["x-api-key"], TESTNOKKEL)
        self.assertEqual(headers["anthropic-version"], ANTHROPIC_VERSION)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertNotIn(
            "Authorization", headers, "Anthropic bruker x-api-key, ikke Bearer"
        )

    def test_kallet_er_JSON_ikke_skjemadata(self):
        """Odoo 20-regel: ekstern kommunikasjon skal være JSON-basert."""
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        self.assertIn("json", mock_post.call_args.kwargs)
        self.assertNotIn("data", mock_post.call_args.kwargs)

    def test_kallet_har_ALLTID_tidsavbrudd(self):
        """🔴 Uten timeout kan én treg AI-forespørsel henge en Odoo-arbeider for
        alltid. Det tar ned hele basen, ikke bare co-worker-panelet."""
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        self.assertEqual(mock_post.call_args.kwargs["timeout"], REQUEST_TIMEOUT)
        self.assertGreater(REQUEST_TIMEOUT, 0)

    def test_max_tokens_er_med(self):
        """max_tokens er PÅKREVD av Anthropic — uten den er kallet ugyldig."""
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        self.assertEqual(
            mock_post.call_args.kwargs["json"]["max_tokens"], DEFAULT_MAX_TOKENS
        )

    def test_default_modell_uten_datosuffiks(self):
        """Modell-id-en er nøyaktig «claude-opus-4-8» — et datosuffiks gir 404."""
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        modell = mock_post.call_args.kwargs["json"]["model"]
        self.assertEqual(modell, DEFAULT_MODEL)
        self.assertEqual(modell, "claude-opus-4-8")

    def test_modell_kan_settes_via_systemparameter(self):
        """Config-drevet — admin skal kunne bytte modell uten kodeendring."""
        self.icp.set_param(PARAM_MODEL, "claude-haiku-4-5")
        self.addCleanup(self.icp.set_param, PARAM_MODEL, "")
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        self.assertEqual(
            mock_post.call_args.kwargs["json"]["model"], "claude-haiku-4-5"
        )

    def test_blank_modellparameter_faller_tilbake_til_default(self):
        """🔴 En tømt parameter skal ikke gi tom modell-id — det er en 400 på hvert kall."""
        self.icp.set_param(PARAM_MODEL, "   ")
        self.addCleanup(self.icp.set_param, PARAM_MODEL, "")
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        self.assertEqual(mock_post.call_args.kwargs["json"]["model"], DEFAULT_MODEL)

    def test_meldingen_trimmes_og_sendes_som_bruker(self):
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("  Hva er FIQ?  ")
        meldinger = mock_post.call_args.kwargs["json"]["messages"]
        self.assertEqual(meldinger, [{"role": "user", "content": "Hva er FIQ?"}])

    def test_systemnotatet_navngir_den_innloggede_brukeren(self):
        """Svaret skal kunne tilpasses — men ALDRI gi tilgang til data brukeren
        ikke allerede ser. Vi sender navnet, ikke rettigheter eller e-post."""
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        system = mock_post.call_args.kwargs["json"]["system"]
        self.assertIn(self.env.user.name, system)
        self.assertNotIn(
            self.env.user.login,
            system,
            "Innloggingsnavnet skal ikke sendes til Anthropic",
        )

    def test_kontekst_legges_paa_systemnotatet(self):
        """Kontekst fra flaten skal utvide systemnotatet, ikke erstatte det."""
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei", kontekst="Brukeren står i Regnskapsflaten.")
        system = mock_post.call_args.kwargs["json"]["system"]
        self.assertIn("Regnskapsflaten", system)
        self.assertIn(
            self.env.user.name,
            system,
            "Kontekst skal LEGGES TIL, ikke overskrive systemnotatet",
        )

    def test_ikke_streng_kontekst_kaster_ikke(self):
        """FEILSTI: flaten kan sende en dict eller et tall. Skal ikke felle kallet."""
        for kontekst in ({"flate": "rgs"}, 42, ["a", "b"]):
            with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
                svar = self.Assistent.spor("Hei", kontekst=kontekst)
            self.assertIsInstance(svar, str)
            self.assertIsInstance(mock_post.call_args.kwargs["json"]["system"], str)

    # ---------- Vellykket svar ----------

    def test_tekstsvar_returneres_som_ren_tekst(self):
        with patch(MOCK_POST, return_value=_tekstsvar("FIQ er en AI-plattform.")):
            self.assertEqual(
                self.Assistent.spor("Hva er FIQ?"), "FIQ er en AI-plattform."
            )

    def test_flere_tekstblokker_slaas_sammen(self):
        svar = _respons(
            {
                "content": [
                    {"type": "text", "text": "Del 1. "},
                    {"type": "text", "text": "Del 2."},
                ]
            }
        )
        with patch(MOCK_POST, return_value=svar):
            self.assertEqual(self.Assistent.spor("Hei"), "Del 1. Del 2.")

    def test_ikke_tekst_blokker_hoppes_over(self):
        """Et tool_use- eller thinking-blokk skal ikke havne i brukerens svar."""
        svar = _respons(
            {
                "content": [
                    {"type": "thinking", "thinking": "intern resonnering"},
                    {"type": "text", "text": "Det endelige svaret."},
                    {"type": "tool_use", "id": "t1", "name": "f", "input": {}},
                ]
            }
        )
        with patch(MOCK_POST, return_value=svar):
            resultat = self.Assistent.spor("Hei")
        self.assertEqual(resultat, "Det endelige svaret.")
        self.assertNotIn("intern resonnering", resultat)

    # ---------- 🔴 FEILSTIEN: ALDRI kast ----------

    def test_timeout_gir_lesbar_beskjed_uten_aa_kaste(self):
        """🔴 KONTRAKTEN. Kaster den her, dør hele co-worker-panelet."""
        with patch(MOCK_POST, side_effect=requests.exceptions.Timeout("tidsavbrudd")):
            svar = self.Assistent.spor("Hei")
        self.assertIsInstance(svar, str)
        self.assertTrue(svar.strip(), "Brukeren fikk ingen beskjed i det hele tatt")

    def test_tilkoblingsfeil_gir_lesbar_beskjed(self):
        with patch(MOCK_POST, side_effect=requests.exceptions.ConnectionError("nede")):
            svar = self.Assistent.spor("Hei")
        self.assertIsInstance(svar, str)
        self.assertTrue(svar.strip())

    def test_http_feil_gir_lesbar_beskjed(self):
        """401/429/500 — `raise_for_status()` kaster HTTPError, en RequestException."""
        for status in ("401 Unauthorized", "429 Too Many Requests", "500 Server Error"):
            feilsvar = _respons(raise_for_status=requests.exceptions.HTTPError(status))
            with patch(MOCK_POST, return_value=feilsvar):
                svar = self.Assistent.spor("Hei")
            self.assertIsInstance(svar, str, f"HTTP {status} felte kallet")
            self.assertTrue(svar.strip())

    def test_ugyldig_JSON_gir_lesbar_beskjed(self):
        """🔴 FEILSTI: en proxy eller feilside gir HTML i stedet for JSON.
        `resp.json()` kaster ValueError — den skal fanges, ikke boble opp."""
        soppel = _respons(json_exception=ValueError("Expecting value: line 1 column 1"))
        with patch(MOCK_POST, return_value=soppel):
            svar = self.Assistent.spor("Hei")
        self.assertIsInstance(svar, str)
        self.assertTrue(svar.strip())

    def test_uventet_payload_form_kaster_ikke(self):
        """🔴 FEILSTI: gyldig JSON, men feil FORM (liste, streng, tall).
        `data.get(...)` ville gitt AttributeError rett i brukerens ansikt."""
        for soppel in ([], ["a"], "en streng", 42, None):
            with patch(MOCK_POST, return_value=_respons(soppel)):
                svar = self.Assistent.spor("Hei")
            self.assertIsInstance(svar, str, f"Payload {soppel!r} felte kallet")
            self.assertTrue(svar.strip(), f"Payload {soppel!r} ga tomt svar")

    def test_blokker_som_ikke_er_dict_kaster_ikke(self):
        """FEILSTI: content-lista inneholder noe annet enn objekter."""
        with patch(
            MOCK_POST, return_value=_respons({"content": ["ikke et objekt", None, 3]})
        ):
            svar = self.Assistent.spor("Hei")
        self.assertIsInstance(svar, str)
        self.assertTrue(svar.strip())

    def test_tomt_svar_forklares_ikke_bare_tom_streng(self):
        """🔴 Brukeren må se FORSKJELL på «AI-en svarte ingenting» og «ingenting skjedde»."""
        for tomt in (
            {"content": []},
            {"content": [{"type": "text", "text": "   "}]},
            {"stop_reason": "end_turn"},
        ):
            with patch(MOCK_POST, return_value=_respons(tomt)):
                svar = self.Assistent.spor("Hei")
            self.assertTrue(
                svar.strip(), f"Tomt svar {tomt!r} ga tom streng til brukeren"
            )

    def test_spor_kaster_ALDRI_uansett_feil(self):
        """🔴 SAMLETESTEN for kontrakten: hver tenkelige feil, ingen skal boble opp."""
        feil = [
            requests.exceptions.Timeout("timeout"),
            requests.exceptions.ConnectTimeout("connect timeout"),
            requests.exceptions.ReadTimeout("read timeout"),
            requests.exceptions.ConnectionError("connection error"),
            requests.exceptions.SSLError("ssl error"),
            requests.exceptions.TooManyRedirects("redirects"),
            requests.exceptions.HTTPError("http error"),
            requests.exceptions.RequestException("generisk"),
        ]
        for e in feil:
            with patch(MOCK_POST, side_effect=e):
                try:
                    svar = self.Assistent.spor("Hei")
                except Exception as boblet:  # noqa: BLE001 — DET er hele poenget
                    self.fail(
                        f"spor() kastet {boblet!r} ved {e!r} — kontrakten er brutt"
                    )
            self.assertIsInstance(svar, str)
            self.assertTrue(svar.strip())

    # ---------- 🔴 SIKKERHET: nøkkelen ----------

    def test_noekkelen_logges_ALDRI_ved_vellykket_kall(self):
        with patch(MOCK_POST, return_value=_tekstsvar()):
            with self.assertLogs("odoo.addons.fiq_gui_ai", level="DEBUG") as logg:
                # tvinger minst én logglinje så assertLogs ikke feiler på tomhet
                import logging

                logging.getLogger("odoo.addons.fiq_gui_ai").debug("testmarkør")
                self.Assistent.spor("Hei")
        alt = "\n".join(logg.output)
        self.assertNotIn(TESTNOKKEL, alt, "API-NØKKELEN BLE LOGGET")
        self.assertNotIn("sk-ant", alt)

    def test_noekkelen_logges_ALDRI_naar_kallet_FEILER(self):
        """🔴 SIKKERHET, feilstien: her logges det faktisk (`_logger.warning`).
        Inneholder unntaket forespørselen, kan nøkkelen følge med i loggen."""
        e = requests.exceptions.HTTPError(
            "401 for url https://api.anthropic.com/v1/messages "
            f"(x-api-key: {TESTNOKKEL})"
        )
        with patch(MOCK_POST, side_effect=e):
            with self.assertLogs("odoo.addons.fiq_gui_ai", level="WARNING") as logg:
                svar = self.Assistent.spor("Hei")
        alt = "\n".join(logg.output)
        self.assertNotIn(
            TESTNOKKEL,
            alt,
            "API-NØKKELEN BLE LOGGET I FEILSTIEN — den ligger nå i "
            "Odoo.sh-loggen i klartekst",
        )
        self.assertNotIn(
            TESTNOKKEL, svar, "API-NØKKELEN BLE VIST TIL BRUKEREN i feilmeldingen"
        )

    def test_noekkelen_returneres_ALDRI_til_brukeren(self):
        """🔴 SIKKERHET: returverdien går rett inn i co-worker-panelet."""
        tilfeller = [
            ("vellykket", {"return_value": _tekstsvar("Alt fint")}),
            (
                "http-feil",
                {"side_effect": requests.exceptions.HTTPError(f"401 key={TESTNOKKEL}")},
            ),
            (
                "json-feil",
                {"return_value": _respons(json_exception=ValueError(TESTNOKKEL))},
            ),
            ("soppel", {"return_value": _respons(["søppel"])}),
        ]
        for navn, kwargs in tilfeller:
            with patch(MOCK_POST, **kwargs):
                svar = self.Assistent.spor("Hei")
            self.assertNotIn(TESTNOKKEL, svar, f"Nøkkelen lekket i tilfellet «{navn}»")
            self.assertNotIn("sk-ant", svar, f"Nøkkel-form lekket i tilfellet «{navn}»")

    def test_noekkelen_er_KUN_i_headeren_aldri_i_kroppen(self):
        """🔴 SIKKERHET: bodyen logges av mellomledd; headeren gjør det sjeldnere."""
        import json as _json

        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        kropp = _json.dumps(mock_post.call_args.kwargs["json"])
        self.assertNotIn(TESTNOKKEL, kropp)
        self.assertNotIn("sk-ant", kropp)

    def test_noekkelen_havner_ikke_i_URLen(self):
        """🔴 SIKKERHET: URL-er logges av ALT — proxy, brannmur, Odoo.sh."""
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        url = mock_post.call_args.args[0]
        self.assertNotIn(TESTNOKKEL, url)
        self.assertNotIn("?", url, "Ingen spørringsparametere skal på Anthropic-URL-en")

    def test_noekkelen_leses_fra_config_aldri_hardkodet(self):
        """Bytter admin nøkkelen, skal NESTE kall bruke den nye — ingen mellomlagring."""
        ny = "sk-ant-api03-HELT-NY-NOKKEL-0000"
        self.icp.set_param(PARAM_KEY, ny)
        with patch(MOCK_POST, return_value=_tekstsvar()) as mock_post:
            self.Assistent.spor("Hei")
        self.assertEqual(mock_post.call_args.kwargs["headers"]["x-api-key"], ny)


@tagged("post_install", "-at_install", "fiq_gui_ai")
class TestFiqGuiAiTilstedevaerelse(TransactionCase):
    """`get_tilstedevaerelse()` — hvem er pålogget. Tester OPPRETTER egne brukere."""

    def setUp(self):
        super().setUp()
        self.Assistent = self.env["fiq.gui.ai.assistent"]
        # OPPRETT vår egen tilstand — ikke stol på hvilke brukere basen har.
        self.firma_a = self.env["res.company"].create({"name": "FIQ Testfirma A"})
        self.firma_b = self.env["res.company"].create({"name": "FIQ Testfirma B"})
        self.intern = self.env["res.users"].create(
            {
                "name": "FIQ Testbruker Intern",
                "login": "fiq_test_intern@example.com",
                "company_id": self.firma_a.id,
                "company_ids": [(6, 0, [self.firma_a.id])],
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.intern_b = self.env["res.users"].create(
            {
                "name": "FIQ Testbruker Firma B",
                "login": "fiq_test_firma_b@example.com",
                "company_id": self.firma_b.id,
                "company_ids": [(6, 0, [self.firma_b.id])],
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

    def test_returnerer_liste_med_forventede_noekler(self):
        """Flaten leser id/name/status/online/is_me — mangler én, krasjer OWL-malen."""
        rader = self.Assistent.get_tilstedevaerelse()
        self.assertIsInstance(rader, list)
        self.assertTrue(rader, "Vi opprettet brukere — lista skal ikke være tom")
        for rad in rader:
            self.assertEqual(set(rad), {"id", "name", "status", "online", "is_me"})

    def test_egen_opprettet_bruker_er_med(self):
        """Beviser at metoden faktisk plukker opp NY tilstand, ikke bare gammel data."""
        navn = [r["name"] for r in self.Assistent.get_tilstedevaerelse()]
        self.assertIn("FIQ Testbruker Intern", navn)

    def test_portalbrukere_utelates(self):
        """🔴 Portal-/delte brukere er KUNDER. De skal aldri stå i et internt
        tilstedeværelsespanel — det er en lekkasje av hvem som er kunde."""
        portal = self.env["res.users"].create(
            {
                "name": "FIQ Testportal Kunde",
                "login": "fiq_test_portal@example.com",
                "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
            }
        )
        navn = [r["name"] for r in self.Assistent.get_tilstedevaerelse()]
        self.assertNotIn(portal.name, navn, "En portalbruker lekket inn i panelet")

    def test_deaktiverte_brukere_utelates(self):
        """En sluttet ansatt skal ikke stå i panelet."""
        self.intern.active = False
        navn = [r["name"] for r in self.Assistent.get_tilstedevaerelse()]
        self.assertNotIn("FIQ Testbruker Intern", navn)

    def test_is_me_peker_paa_den_innloggede(self):
        """«meg» skal merkes i lista så flaten kan løfte deg fram.

        ⚠️ LÆRDOM fra første kjøring (verifisert mot basen, ikke antatt): testen
        kjørte først som testkjørerens standardbruker — uid 1 «OdooBot», som er
        `active = false` i denne basen. Metoden filtrerer bort inaktive, så «meg»
        var korrekt fraværende og testen feilet på sin egen antagelse.
        FEILEN LÅ I TESTEN. Vi kjører som en AKTIV bruker vi selv har opprettet —
        det er også Port 6-disiplin: test din egen tilstand, ikke basens tilfeldige."""
        rader = self.Assistent.with_user(self.intern).get_tilstedevaerelse()
        meg = [r for r in rader if r["is_me"]]
        self.assertEqual(len(meg), 1, "Nøyaktig én rad skal være «meg»")
        self.assertEqual(meg[0]["id"], self.intern.id)

    def test_inaktiv_innlogget_bruker_er_ikke_med_i_egen_liste(self):
        """Dokumenterer den faktiske oppførselen funnet over: er DU selv inaktiv,
        står du ikke i panelet. Det er riktig — inaktive skal ikke vises — men det
        betyr at «meg»-raden kan mangle helt. Flaten må tåle det."""
        self.intern.active = False
        rader = self.Assistent.with_user(self.intern).get_tilstedevaerelse()
        self.assertEqual(
            [r for r in rader if r["is_me"]],
            [],
            "En inaktiv bruker skal ikke stå i sitt eget panel",
        )

    def test_ingen_PII_utover_navnet(self):
        """🔴 GDPR: panelet skal vise navn og status — ALDRI e-post, telefon eller
        innlogging. Feltene under er ikke i kontrakten, og skal ikke snike seg inn."""
        rader = self.Assistent.get_tilstedevaerelse()
        forbudt = {"login", "email", "phone", "mobile", "partner_id", "password"}
        for rad in rader:
            self.assertFalse(
                set(rad) & forbudt,
                "PII lekket i tilstedeværelsen: %s" % (set(rad) & forbudt),
            )
        raa = str(rader)
        self.assertNotIn(
            "fiq_test_intern@example.com", raa, "Innloggings-e-posten lekket i panelet"
        )

    def test_status_er_en_kjent_verdi(self):
        gyldige = {"online", "away", "offline"}
        for rad in self.Assistent.get_tilstedevaerelse():
            self.assertIn(
                rad["status"],
                gyldige,
                "Ukjent status «{}» — flaten kjenner bare {}".format(
                    rad["status"], gyldige
                ),
            )

    def test_online_flagget_foelger_status(self):
        for rad in self.Assistent.get_tilstedevaerelse():
            self.assertEqual(rad["online"], rad["status"] in ("online", "away"))

    def test_sortering_paalogget_foerst_deretter_alfabetisk(self):
        """Panelet skal vise pålogget øverst — ellers må brukeren lete."""
        rader = self.Assistent.get_tilstedevaerelse()
        rank = {"online": 0, "away": 1, "offline": 2}
        noekler = [(rank.get(r["status"], 3), r["name"].lower()) for r in rader]
        self.assertEqual(noekler, sorted(noekler), "Tilstedeværelsen er feilsortert")

    def test_kjoerer_som_den_innloggede_brukeren(self):
        """🔴 TENANT-DISIPLIN: metoden skal IKKE sudo-e. Kjører den som innlogget
        bruker, styrer Odoos regler hva som er synlig — og et firma kan aldri se
        et annet firmas brukere gjennom co-worker-panelet."""
        som_intern = self.Assistent.with_user(self.intern)
        rader = som_intern.get_tilstedevaerelse()
        self.assertIsInstance(rader, list)
        meg = [r for r in rader if r["is_me"]]
        self.assertEqual(len(meg), 1)
        self.assertEqual(
            meg[0]["id"],
            self.intern.id,
            "«is_me» pekte ikke på den brukeren metoden kjørte som — "
            "da er self.env.uid ikke den innloggede",
        )

    def test_firma_bytte_endrer_ikke_is_me(self):
        """Firma-scope: bytter brukeren aktivt firma, er han fortsatt seg selv."""
        som_b = self.Assistent.with_user(self.intern_b).with_company(self.firma_b)
        rader = som_b.get_tilstedevaerelse()
        meg = [r for r in rader if r["is_me"]]
        self.assertEqual(len(meg), 1)
        self.assertEqual(meg[0]["id"], self.intern_b.id)


@tagged("post_install", "-at_install", "fiq_gui_ai")
class TestFiqGuiAiTilgang(TransactionCase):
    """Tilgangsgruppene — «AI MGM» styrer konfigurasjon, chatten er åpen for alle."""

    def test_ai_mgm_gruppen_finnes_og_er_synlig(self):
        """🔴 En res.groups UTEN privilege_id er USYNLIG i Innstillinger > Brukere —
        den virker, men ingen kan huke den av. Samme felle som felte
        fiq_gui_control v6.77 og fiq_tilgang v1.2.0."""
        gruppe = self.env.ref("fiq_gui_ai.group_ai_mgm")
        self.assertTrue(
            gruppe.privilege_id,
            "AI MGM mangler privilege_id — gruppa er usynlig i brukerskjemaet",
        )
        self.assertTrue(gruppe.privilege_id.category_id)

    def test_ai_mgm_arver_intern_bruker(self):
        gruppe = self.env.ref("fiq_gui_ai.group_ai_mgm")
        self.assertIn(self.env.ref("base.group_user"), gruppe.implied_ids)

    def test_systemadmin_har_ai_mgm(self):
        """Admin må kunne sette nøkkelen uten at noen deler ut gruppa manuelt."""
        admin = self.env.ref("base.user_admin")
        self.assertTrue(admin.has_group("fiq_gui_ai.group_ai_mgm"))

    def test_vanlig_intern_bruker_naar_chatten(self):
        """Chatten skal være åpen for alle interne — den er poenget med flaten."""
        bruker = self.env["res.users"].create(
            {
                "name": "FIQ Testbruker Chat",
                "login": "fiq_test_chat@example.com",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(PARAM_KEY, TESTNOKKEL)
        self.addCleanup(icp.set_param, PARAM_KEY, "")
        with patch(MOCK_POST, return_value=_tekstsvar("Hei!")):
            svar = self.env["fiq.gui.ai.assistent"].with_user(bruker).spor("Hei")
        self.assertEqual(svar, "Hei!")
