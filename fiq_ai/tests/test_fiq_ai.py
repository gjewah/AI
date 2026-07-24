"""Tester for FIQ AI-shimen (`fiq.ai`) og oppsett-wizarden.

HVA MODULEN GJØR: `fiq.ai.chat(q) -> str` er ÉN AI-vei fra Kontrollrommet («Spør
AI») ned til Odoo 19s native AI-tjeneste, som `fiq_ai_claude` ruter til Anthropic.
Shimen legger på FIQ-grunningen (system-konteksten) og har ingen egen HTTP-klient.

HVORFOR TESTENE FINNES:
  * Shimen er den ENESTE grunningsstedet. Faller FIQ-konteksten bort, svarer
    «Spør AI» generisk og vet ikke hva FIQ er — feilen er stille og synes bare
    på svarkvaliteten.
  * Grunningen er config-drevet (`fiq_ai.system_context`) med modul-konstant som
    durabel fallback. Begge grener må virke.
  * Wizarden håndterer API-NØKKELEN. Den skal lagres, testes — og deretter
    slettes fra wizard-recorden. Blir den liggende, ligger nøkkelen i klartekst
    i en transient tabell.

PORT 6-disiplin: hver test OPPRETTER sin egen tilstand (systemparametere,
wizard-poster). Ingen test leser bare det basen tilfeldigvis har.

INGEN NETTVERK: `fiq.ai.chat` mockes på `LLMApiService._request` (HTTP-laget) —
da testes HELE vår vei ned til, men ikke ut på, nettet.
"""

from unittest.mock import patch

from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.fiq_ai.models.fiq_ai import FIQ_SPORAI_CONTEXT
from odoo.addons.fiq_ai.wizards.fiq_ai_setup import CONSOLE_URL, KEY_PARAM
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

TESTNOKKEL = "sk-ant-api03-FIQ-WIZARD-TESTNOKKEL-9876543210"

SVAR_OK = {
    "id": "msg_01FIQ",
    "type": "message",
    "role": "assistant",
    "content": [{"type": "text", "text": "OK"}],
    "stop_reason": "end_turn",
}


@tagged("post_install", "-at_install", "fiq_ai")
class TestFiqAiShim(TransactionCase):
    """`fiq.ai.chat()` — grunning, delegering og feilsti."""

    def setUp(self):
        super().setUp()
        self.Ai = self.env["fiq.ai"]
        self.icp = self.env["ir.config_parameter"].sudo()
        # OPPRETT vår egen tilstand: nøkkel satt, ingen overstyrt kontekst.
        self.icp.set_param("ai.anthropic_key", TESTNOKKEL)
        self.icp.set_param("fiq_ai.system_context", "")
        self.addCleanup(self.icp.set_param, "ai.anthropic_key", "")

    def _svar(self, tekst="Svar."):
        return {"content": [{"type": "text", "text": tekst}]}

    # ---------- Modellen finnes og er abstrakt ----------

    def test_modellen_er_abstrakt(self):
        """Shimen skal ikke lage tabell — den er en ren tjeneste."""
        self.assertTrue(self.Ai._abstract, "fiq.ai skal være en AbstractModel")

    # ---------- Tom inndata ----------

    def test_tomt_spoersmaal_ringer_ikke_ut(self):
        """🔴 Et tomt felt skal ALDRI koste et API-kall. Blir det sendt, betaler
        FIQ for hver gang en bruker trykker send ved et uhell."""
        with patch.object(LLMApiService, "_request") as mock_req:
            for tomt in ("", "   ", "\n\t ", None):
                self.assertEqual(
                    self.Ai.chat(tomt), "", f"Tomt spørsmål {tomt!r} ga ikke tom streng"
                )
            mock_req.assert_not_called()

    # ---------- Grunningen ----------

    def test_default_grunning_er_FIQ_konteksten(self):
        """🔴 KJERNEN: uten system-prompt vet «Spør AI» ikke hva FIQ er."""
        with patch.object(
            LLMApiService, "_request", return_value=self._svar()
        ) as mock_req:
            self.Ai.chat("Hva er FIQ?")
        system = mock_req.call_args.kwargs["body"]["system"]
        self.assertEqual(system, FIQ_SPORAI_CONTEXT)

    def test_grunningen_inneholder_de_baerende_FIQ_faktaene(self):
        """Konstanten er en durabel fallback — endres den, skal den fortsatt bære
        hierarki, membran-regel og at Vidir IKKE er hoved."""
        for fakta in ("FIQ AI", "membran", "Vidir", "bokmål"):
            self.assertIn(
                fakta.lower(),
                FIQ_SPORAI_CONTEXT.lower(),
                f"FIQ-grunningen mangler «{fakta}»",
            )

    def test_systemparameter_overstyrer_grunningen(self):
        """Config-drevet: en tenant skal kunne endre konteksten uten kodeendring."""
        self.icp.set_param("fiq_ai.system_context", "EGEN KONTEKST FOR TEST")
        self.addCleanup(self.icp.set_param, "fiq_ai.system_context", "")
        with patch.object(
            LLMApiService, "_request", return_value=self._svar()
        ) as mock_req:
            self.Ai.chat("Hei")
        self.assertEqual(
            mock_req.call_args.kwargs["body"]["system"], "EGEN KONTEKST FOR TEST"
        )

    def test_tom_systemparameter_faller_tilbake_til_konstanten(self):
        """🔴 En tømt systemparam skal ikke gi TOM grunning — da mister «Spør AI»
        all FIQ-bevissthet uten at noen ser det."""
        self.icp.set_param("fiq_ai.system_context", "")
        with patch.object(
            LLMApiService, "_request", return_value=self._svar()
        ) as mock_req:
            self.Ai.chat("Hei")
        self.assertEqual(
            mock_req.call_args.kwargs["body"]["system"], FIQ_SPORAI_CONTEXT
        )

    def test_eksplisitt_system_argument_vinner(self):
        """Kalleren kan sende egen grunning (Meldingssenter/Salg)."""
        with patch.object(
            LLMApiService, "_request", return_value=self._svar()
        ) as mock_req:
            self.Ai.chat("Hei", system="Du er en salgsassistent.")
        self.assertEqual(
            mock_req.call_args.kwargs["body"]["system"], "Du er en salgsassistent."
        )

    def test_tom_streng_som_system_gir_ingen_grunning(self):
        """system='' er en BEVISST tom grunning (ikke None) — den skal respekteres.
        Anthropic utelater da system-feltet helt."""
        with patch.object(
            LLMApiService, "_request", return_value=self._svar()
        ) as mock_req:
            self.Ai.chat("Hei", system="")
        self.assertNotIn("system", mock_req.call_args.kwargs["body"])

    # ---------- Delegering ----------

    def test_default_modell_brukes(self):
        with patch.object(
            LLMApiService, "_request", return_value=self._svar()
        ) as mock_req:
            self.Ai.chat("Hei")
        self.assertEqual(mock_req.call_args.kwargs["body"]["model"], "claude-sonnet-5")

    def test_modell_kan_overstyres(self):
        with patch.object(
            LLMApiService, "_request", return_value=self._svar()
        ) as mock_req:
            self.Ai.chat("Hei", model="claude-opus-4-8")
        self.assertEqual(mock_req.call_args.kwargs["body"]["model"], "claude-opus-4-8")

    def test_shimen_bruker_anthropic_veien(self):
        """🔴 ÉN AI-vei: shimen skal treffe /messages, ikke OpenAIs /responses."""
        with patch.object(
            LLMApiService, "_request", return_value=self._svar()
        ) as mock_req:
            self.Ai.chat("Hei")
        self.assertEqual(mock_req.call_args.kwargs["endpoint"], "/messages")

    def test_spoersmaalet_trimmes_og_sendes_som_brukermelding(self):
        with patch.object(
            LLMApiService, "_request", return_value=self._svar()
        ) as mock_req:
            self.Ai.chat("   Hva er FIQ?   ")
        melding = mock_req.call_args.kwargs["body"]["messages"][0]
        self.assertEqual(melding["role"], "user")
        self.assertEqual(melding["content"][0]["text"], "Hva er FIQ?")

    # ---------- Svaret ----------

    def test_tekstsvar_returneres_som_ren_streng(self):
        with patch.object(
            LLMApiService, "_request", return_value=self._svar("Hei igjen.")
        ):
            self.assertEqual(self.Ai.chat("Hei"), "Hei igjen.")

    def test_flere_tekstblokker_slaas_sammen_med_linjeskift(self):
        svar = {
            "content": [
                {"type": "text", "text": "Linje 1"},
                {"type": "text", "text": "Linje 2"},
            ]
        }
        with patch.object(LLMApiService, "_request", return_value=svar):
            self.assertEqual(self.Ai.chat("Hei"), "Linje 1\nLinje 2")

    def test_tomt_svar_gir_lesbar_plassholder_ikke_tom_streng(self):
        """🔴 Brukeren må se FORSKJELL på «AI-en svarte ingenting» og «ingenting skjedde»."""
        for tomt in ({"content": []}, {"content": [{"type": "text", "text": "   "}]}):
            with patch.object(LLMApiService, "_request", return_value=tomt):
                self.assertEqual(self.Ai.chat("Hei"), "(tomt svar)")

    def test_svaret_lekker_ikke_noekkelen(self):
        """🔴 SIKKERHET: returverdien går rett i brukerflaten."""
        with patch.object(
            LLMApiService, "_request", return_value=self._svar("Alt fint")
        ):
            svar = self.Ai.chat("Hei")
        self.assertNotIn(TESTNOKKEL, svar)
        self.assertNotIn("sk-ant", svar)

    def test_noekkelen_logges_ikke_av_shimen(self):
        """🔴 SIKKERHETSTEST for hele fiq_ai-veien."""
        with patch.object(LLMApiService, "_request", return_value=self._svar()):
            with self.assertLogs("odoo.addons", level="DEBUG") as logg:
                self.Ai.chat("Hei")
        alt = "\n".join(logg.output)
        self.assertNotIn(TESTNOKKEL, alt, "API-NØKKELEN BLE LOGGET")
        self.assertNotIn("sk-ant", alt)

    # ---------- FEILSTIEN ----------

    def test_manglende_noekkel_kastes_videre_som_UserError(self):
        """🔴 Dokumentert kontrakt: shimen KASTER videre — «Spør AI» viser feilen i
        klartekst. Svelges den, får brukeren «(tomt svar)» og ingen anelse om
        at nøkkelen mangler."""
        self.icp.set_param("ai.anthropic_key", "")
        with patch.dict("os.environ", {}, clear=False) as miljo:
            miljo.pop("ANTHROPIC_API_KEY", None)
            with self.assertRaises(UserError) as ctx:
                self.Ai.chat("Hei")
        self.assertIn("ai.anthropic_key", str(ctx.exception))
        self.assertNotIn("sk-ant", str(ctx.exception))

    def test_timeout_kastes_videre(self):
        """FEILSTI: nettet henger → UserError til brukeren, ikke et falskt svar."""
        with patch.object(
            LLMApiService, "_request", side_effect=UserError("Timeout mot Anthropic")
        ):
            with self.assertRaises(UserError):
                self.Ai.chat("Hei")

    def test_http_feil_kastes_videre(self):
        with patch.object(
            LLMApiService, "_request", side_effect=UserError("429 rate_limit_error")
        ):
            with self.assertRaises(UserError) as ctx:
                self.Ai.chat("Hei")
        self.assertIn("429", str(ctx.exception))

    def test_api_feilsvar_kastes_videre(self):
        """{"type":"error"} med HTTP 200 må ikke bli til et tomt, «vellykket» svar."""
        feil = {
            "type": "error",
            "error": {"type": "overloaded_error", "message": "Overloaded"},
        }
        with patch.object(LLMApiService, "_request", return_value=feil):
            with self.assertRaises(ValueError):
                self.Ai.chat("Hei")


@tagged("post_install", "-at_install", "fiq_ai")
class TestFiqAiSetupWizard(TransactionCase):
    """2-stegs oppsett-wizarden for Claude-nøkkelen."""

    def setUp(self):
        super().setUp()
        self.Wizard = self.env["fiq.ai.setup.wizard"]
        self.icp = self.env["ir.config_parameter"].sudo()
        # OPPRETT vår egen tilstand: start uten nøkkel.
        self.icp.set_param(KEY_PARAM, "")
        self.addCleanup(self.icp.set_param, KEY_PARAM, "")

    # ---------- Stegflyt ----------

    def test_wizarden_starter_paa_steg1(self):
        wiz = self.Wizard.create({})
        self.assertEqual(wiz.state, "step1")

    def test_neste_og_tilbake_flytter_steg_og_gjenaapner_samme_post(self):
        """Wizarden er target=new — uten `_reopen()` lukkes dialogen på hvert steg."""
        wiz = self.Wizard.create({})
        act = wiz.action_next()
        self.assertEqual(wiz.state, "step2")
        self.assertEqual(act["type"], "ir.actions.act_window")
        self.assertEqual(act["res_model"], "fiq.ai.setup.wizard")
        self.assertEqual(act["res_id"], wiz.id, "Wizarden gjenåpnet en ANNEN post")
        self.assertEqual(act["target"], "new")
        wiz.action_back()
        self.assertEqual(wiz.state, "step1")

    def test_steg1_aapner_anthropic_console(self):
        wiz = self.Wizard.create({})
        act = wiz.action_open_console()
        self.assertEqual(act["type"], "ir.actions.act_url")
        self.assertEqual(act["url"], CONSOLE_URL)
        self.assertEqual(act["target"], "new")

    # ---------- key_is_set ----------

    def test_key_is_set_er_usann_uten_noekkel(self):
        wiz = self.Wizard.create({})
        wiz.invalidate_recordset(["key_is_set"])
        self.assertFalse(wiz.key_is_set)

    def test_key_is_set_blir_sann_naar_noekkel_finnes(self):
        """Flaten viser «nøkkel alt satt» — feil her og admin setter nøkkelen dobbelt."""
        self.icp.set_param(KEY_PARAM, TESTNOKKEL)
        wiz = self.Wizard.create({})
        wiz.invalidate_recordset(["key_is_set"])
        self.assertTrue(wiz.key_is_set)

    def test_key_is_set_avsloerer_ikke_noekkelen(self):
        """🔴 SIKKERHET: feltet er boolsk med vilje. Det skal si OM, ikke HVILKEN."""
        self.icp.set_param(KEY_PARAM, TESTNOKKEL)
        wiz = self.Wizard.create({})
        wiz.invalidate_recordset(["key_is_set"])
        self.assertIs(wiz.key_is_set, True)
        self.assertIsInstance(wiz.key_is_set, bool)

    # ---------- Lagring ----------

    def test_tom_noekkel_avvises(self):
        """Uten nøkkel skal wizarden si fra, ikke lagre en tom systemparam."""
        wiz = self.Wizard.create({"state": "step2", "anthropic_key": "   "})
        with self.assertRaises(UserError) as ctx:
            wiz.action_save_and_test()
        self.assertIn(
            "sk-ant", str(ctx.exception), "Feilmeldingen bør vise nøkkel-formatet"
        )
        self.assertFalse(
            self.icp.get_param(KEY_PARAM), "En tom nøkkel ble likevel lagret"
        )

    def test_noekkel_lagres_i_riktig_systemparameter(self):
        """Nøkkelen MÅ havne i `ai.anthropic_key` — det er den fiq_ai_claude leser."""
        wiz = self.Wizard.create({"state": "step2", "anthropic_key": TESTNOKKEL})
        with patch.object(LLMApiService, "_request", return_value=SVAR_OK):
            wiz.action_save_and_test()
        self.assertEqual(self.icp.get_param(KEY_PARAM), TESTNOKKEL)

    def test_noekkelen_trimmes_foer_lagring(self):
        """🔴 Kopiert fra Console får nøkkelen ofte med mellomrom/linjeskift. Lagres
        de, feiler HVERT kall med 401 og ingen skjønner hvorfor."""
        wiz = self.Wizard.create(
            {"state": "step2", "anthropic_key": "  %s \n" % TESTNOKKEL}
        )
        with patch.object(LLMApiService, "_request", return_value=SVAR_OK):
            wiz.action_save_and_test()
        self.assertEqual(self.icp.get_param(KEY_PARAM), TESTNOKKEL)

    def test_noekkelfeltet_toemmes_etter_lagring(self):
        """🔴 SIKKERHET: `fiq.ai.setup.wizard` er en TransientModel — recorden ligger
        i basen til vacuum rydder. Blir nøkkelen liggende i feltet, ligger den i
        klartekst i en tabell alle med tilgang kan lese."""
        wiz = self.Wizard.create({"state": "step2", "anthropic_key": TESTNOKKEL})
        with patch.object(LLMApiService, "_request", return_value=SVAR_OK):
            wiz.action_save_and_test()
        self.assertFalse(
            wiz.anthropic_key, "API-NØKKELEN BLE LIGGENDE I WIZARD-RECORDEN"
        )

    def test_noekkelfeltet_toemmes_OGSAA_naar_testen_feiler(self):
        """🔴 SIKKERHET, feilstien: nøkkelen må slettes uansett utfall."""
        wiz = self.Wizard.create({"state": "step2", "anthropic_key": TESTNOKKEL})
        with patch.object(
            LLMApiService, "_request", side_effect=UserError("401 authentication_error")
        ):
            wiz.action_save_and_test()
        self.assertFalse(
            wiz.anthropic_key, "Nøkkelen ble liggende i recorden etter en feilet test"
        )

    # ---------- Live-testen ----------

    def test_vellykket_test_vises_til_brukeren(self):
        wiz = self.Wizard.create({"state": "step2", "anthropic_key": TESTNOKKEL})
        with patch.object(LLMApiService, "_request", return_value=SVAR_OK):
            act = wiz.action_save_and_test()
        self.assertIn("OK", wiz.test_result)
        self.assertEqual(act["res_id"], wiz.id)

    def test_feilet_test_KASTER_IKKE_men_forklarer(self):
        """🔴 FEILSTI: en gal nøkkel skal gi en forklaring i flaten, ikke en
        rød Odoo-krasj som skjuler at nøkkelen faktisk BLE lagret."""
        wiz = self.Wizard.create({"state": "step2", "anthropic_key": "sk-ant-feil"})
        with patch.object(
            LLMApiService, "_request", side_effect=UserError("401 authentication_error")
        ):
            act = wiz.action_save_and_test()  # skal IKKE kaste
        self.assertTrue(wiz.test_result)
        self.assertIn("401", wiz.test_result)
        self.assertIn(
            "Anthropic Console",
            wiz.test_result,
            "Brukeren må få vite hva han skal gjøre videre",
        )
        self.assertEqual(act["type"], "ir.actions.act_window")

    def test_timeout_i_testen_kaster_ikke(self):
        """FEILSTI: nettet henger under live-testen."""
        import requests

        wiz = self.Wizard.create({"state": "step2", "anthropic_key": TESTNOKKEL})
        with patch.object(
            LLMApiService,
            "_request",
            side_effect=requests.exceptions.ConnectTimeout("tidsavbrudd"),
        ):
            wiz.action_save_and_test()  # skal IKKE kaste
        self.assertIn("tidsavbrudd", wiz.test_result)

    def test_ugyldig_json_i_testen_kaster_ikke(self):
        """FEILSTI: uleselig svar fra en gateway."""
        wiz = self.Wizard.create({"state": "step2", "anthropic_key": TESTNOKKEL})
        with patch.object(LLMApiService, "_request", return_value="ikke json"):
            wiz.action_save_and_test()  # skal IKKE kaste
        self.assertTrue(
            wiz.test_result, "Brukeren fikk ingen tilbakemelding i det hele tatt"
        )

    def test_testresultatet_lekker_ALDRI_noekkelen(self):
        """🔴 SIKKERHETSTEST: `test_result` vises rett i skjemaet og lagres i basen.
        Ekko-er feilmeldingen fra Anthropic nøkkelen, står den der i klartekst."""
        wiz = self.Wizard.create({"state": "step2", "anthropic_key": TESTNOKKEL})
        with patch.object(
            LLMApiService,
            "_request",
            side_effect=UserError("invalid key: %s" % TESTNOKKEL),
        ):
            wiz.action_save_and_test()
        self.assertNotIn(
            TESTNOKKEL,
            wiz.test_result or "",
            "API-NØKKELEN HAVNET I test_result — synlig i skjemaet",
        )

    def test_live_testen_bruker_FIQ_grunningen(self):
        """Live-testen går gjennom `fiq.ai.chat` — altså samme vei som «Spør AI».
        Tester den en annen vei, beviser den ingenting om den ekte veien."""
        wiz = self.Wizard.create({"state": "step2", "anthropic_key": TESTNOKKEL})
        with patch.object(LLMApiService, "_request", return_value=SVAR_OK) as mock_req:
            wiz.action_save_and_test()
        self.assertEqual(mock_req.call_args.kwargs["endpoint"], "/messages")
        self.assertEqual(
            mock_req.call_args.kwargs["body"]["system"], FIQ_SPORAI_CONTEXT
        )
