# -*- coding: utf-8 -*-
"""Tester for Claude/Anthropic-leverandøren (fiq_ai_claude).

HVA MODULEN GJØR: registrerer «Anthropic (Claude)» i Odoo 19s native AI
(`ai.utils.llm_providers.PROVIDERS`) og monkeypatcher `LLMApiService` slik at
provider «anthropic» ruter til Anthropics **Messages API** (/v1/messages) i
stedet for OpenAIs Responses-API.

HVORFOR TESTENE FINNES:
  * Oversettingen Odoo-kontrakt → Messages-API er ren, deterministisk kode med
    mange grener (verktøy, strukturert JSON, filer, feil-svar). Feiler den, feiler
    ALT AI-arbeid i basen — og det oppdages først når en bruker spør.
  * Patchen er en monkeypatch mot Enterprise-kode. Endrer Odoo signaturen, skal
    testene si fra HER, ikke i produksjon.
  * API-NØKKELEN. Den bygges inn i headeren `x-api-key`. Lekker den til logg,
    feilmelding eller returverdi, er den kompromittert. Det er en sikkerhetsfeil,
    ikke en bug.

PORT 6-disiplin: hver test OPPRETTER sin egen tilstand (systemparametere,
svar-payloader, verktøy-definisjoner). Ingen test leser bare det som tilfeldigvis
finnes i basen.

INGEN NETTVERK: ingen test her ringer ut. `LLMApiService._request` mockes med
`unittest.mock.patch.object` — ClaudeProvider selv er ren python uten HTTP.
"""

import json
from unittest.mock import patch

import requests

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.ai.utils import llm_providers as _lp
from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.fiq_ai_claude.services.anthropic import ClaudeProvider

# Et realistisk, minimalt Messages-svar (formen Anthropic faktisk returnerer).
SVAR_TEKST = {
    "id": "msg_01FIQtest",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-5",
    "content": [{"type": "text", "text": "Hei fra Claude."}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 12, "output_tokens": 5},
}

TESTNOKKEL = "sk-ant-api03-FIQTESTNOKKEL-skal-aldri-lekke-0123456789"


@tagged("post_install", "-at_install", "fiq_ai_claude")
class TestClaudeProvider(TransactionCase):
    """Ren oversetting: Odoos kontrakt → Anthropic Messages-body, og tilbake."""

    # ---------- Identitet / v20-kompatible klassemetoder ----------

    def test_leverandoer_er_registrert_i_odoos_providers(self):
        """Uten registrering finnes ikke Claude-modellene i noe nedtrekk."""
        navn = [getattr(p, "name", None) for p in _lp.PROVIDERS]
        self.assertIn("anthropic", navn,
                      "«anthropic» mangler i ai.utils.llm_providers.PROVIDERS: %s" % navn)

    def test_registrering_er_idempotent(self):
        """Modulen registrerer ved import. Lastes den to ganger (server-restart i
        samme prosess, oppgradering), skal den IKKE dublere leverandøren —
        `get_provider()` returnerer den første treffet og dubletter skjuler feil."""
        from odoo.addons.fiq_ai_claude.models import ai_patch
        antall_for = sum(1 for p in _lp.PROVIDERS if getattr(p, "name", None) == "anthropic")
        ai_patch._register_provider()
        ai_patch._register_provider()
        antall_etter = sum(1 for p in _lp.PROVIDERS if getattr(p, "name", None) == "anthropic")
        self.assertEqual(antall_for, antall_etter, "Leverandøren ble dublert ved ny registrering")
        self.assertEqual(antall_etter, 1, "Det skal finnes nøyaktig ÉN anthropic-leverandør")

    def test_odoo_finner_leverandoer_for_claude_modell(self):
        """Odoos `get_provider(env, model)` må svare «anthropic» for våre modeller —
        det er slik AI-felt/agenter velger vei."""
        for modell, __ in ClaudeProvider.LLMS:
            self.assertEqual(_lp.get_provider(self.env, modell), "anthropic",
                             "Odoo fant ikke anthropic for modellen %s" % modell)

    def test_anthropic_forurenser_ikke_embedding_utvalget(self):
        """🔴 Anthropic har INGEN embeddings. Registreres en tom embedding-modell
        i utvalget, får brukeren et blankt valg som krasjer ved bruk."""
        self.assertEqual(ClaudeProvider.get_embedding_model(), "")
        self.assertEqual(ClaudeProvider.get_transcription_models(), [])
        modeller = [m for m, __ in _lp.EMBEDDING_MODELS_SELECTION]
        self.assertNotIn("", modeller,
                         "Tom embedding-modell havnet i EMBEDDING_MODELS_SELECTION: %s" % modeller)

    def test_respons_stil_mappes_til_modell(self):
        """Odoo velger modell via responsstil. Ukjent stil skal falle tilbake, ikke kaste."""
        self.assertEqual(ClaudeProvider.get_llm_model("slow_and_rigorous"), "claude-opus-4-8")
        self.assertEqual(ClaudeProvider.get_llm_model("snappy_and_creative"), "claude-haiku-4-5")
        self.assertEqual(ClaudeProvider.get_llm_model("standard"), "claude-sonnet-5")
        self.assertEqual(ClaudeProvider.get_llm_model("finnes-ikke"), "claude-sonnet-5",
                         "Ukjent responsstil skal falle tilbake til sonnet, ikke kaste")

    # ---------- Headere: sikkerhet ----------

    def test_headere_har_anthropic_kontrakten(self):
        """x-api-key + anthropic-version er PÅKREVD. Uten dem svarer API-et 401/400."""
        h = ClaudeProvider.build_headers(TESTNOKKEL)
        self.assertEqual(h["x-api-key"], TESTNOKKEL)
        self.assertEqual(h["anthropic-version"], ClaudeProvider.ANTHROPIC_VERSION)
        self.assertEqual(h["content-type"], "application/json")
        self.assertNotIn("Authorization", h,
                         "Anthropic bruker x-api-key, ikke Bearer — OpenAI-headeren skal ikke med")

    def test_noekkel_lekker_ikke_inn_i_meldingskroppen(self):
        """🔴 SIKKERHET: nøkkelen hører hjemme i headeren og INGEN andre steder.
        Havner den i body, blir den logget av alt som logger forespørsler."""
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", ["system"], ["spørsmål"], None, None, None, [], 1024)
        raa = json.dumps(body)
        self.assertNotIn(TESTNOKKEL, raa)
        self.assertNotIn("sk-ant", raa, "Noe nøkkel-lignende havnet i meldingskroppen")

    # ---------- Bygging av Messages-body ----------

    def test_body_har_paakrevde_felt(self):
        """max_tokens er PÅKREVD av Anthropic — uten den er kallet ugyldig."""
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", ["Du er FIQ."], ["Hva er FIQ?"], None, None, None, [], 4096)
        self.assertEqual(body["model"], "claude-sonnet-5")
        self.assertEqual(body["max_tokens"], 4096)
        self.assertEqual(body["system"], "Du er FIQ.")
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertEqual(body["messages"][0]["content"][0]["text"], "Hva er FIQ?")

    def test_temperature_sendes_ALDRI(self):
        """🔴 REGRESJON: `temperature` avvises av Opus 4.8 / Sonnet 5. Sniker den seg
        inn i bodyen, får hvert eneste kall 400 fra API-et."""
        body = ClaudeProvider.build_message_body(
            "claude-opus-4-8", ["s"], ["u"], None, None, None, [], 1024)
        self.assertNotIn("temperature", body)

    def test_flere_system_prompter_slaas_sammen(self):
        """Odoo sender en LISTE av system-prompter; Anthropic tar ÉN streng."""
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", ["Del A", "", "Del B", None], ["u"], None, None, None, [], 1024)
        self.assertEqual(body["system"], "Del A\n\nDel B",
                         "Tomme system-prompter skal filtreres bort, ikke gi doble linjeskift")

    def test_uten_system_prompt_utelates_feltet(self):
        """Tom `system`-nøkkel er en API-feil hos Anthropic — feltet skal utelates helt."""
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", [], ["u"], None, None, None, [], 1024)
        self.assertNotIn("system", body)

    def test_tomt_brukerinnhold_gir_likevel_gyldig_blokk(self):
        """Anthropic avviser en melding med tom content-liste. Vi må sende noe."""
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", ["s"], [], None, None, None, [], 1024)
        innhold = body["messages"][0]["content"]
        self.assertTrue(innhold, "content-lista må aldri være tom")
        self.assertEqual(innhold[0]["type"], "text")

    def test_filer_oversettes_til_riktige_blokktyper(self):
        """Bilde → image/base64, PDF → document/base64, tekst → text. Feil type = 400."""
        filer = [
            {"mimetype": "text/plain", "value": "ren tekst"},
            {"mimetype": "image/png", "value": "aW1n"},
            {"mimetype": "application/pdf", "value": "cGRm"},
        ]
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", ["s"], ["u"], None, filer, None, [], 1024)
        typer = [b["type"] for b in body["messages"][0]["content"]]
        self.assertEqual(typer, ["text", "text", "image", "document"])
        bilde = body["messages"][0]["content"][2]
        self.assertEqual(bilde["source"]["media_type"], "image/png")
        self.assertEqual(bilde["source"]["type"], "base64")
        pdf = body["messages"][0]["content"][3]
        self.assertEqual(pdf["source"]["media_type"], "application/pdf")

    def test_ukjent_mimetype_degraderer_til_tekst_uten_aa_kaste(self):
        """En ukjent filtype skal ikke felle hele kallet."""
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", ["s"], ["u"],
            None, [{"mimetype": "application/x-ukjent", "value": 42}], None, [], 1024)
        siste = body["messages"][0]["content"][-1]
        self.assertEqual(siste["type"], "text")
        self.assertEqual(siste["text"], "42")

    def test_verktoey_oversettes_til_anthropic_format(self):
        """Odoos tools-dict {navn: (beskrivelse, allow_end, callable, schema)}
        → Anthropic {name, description, input_schema}."""
        schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
        tools = {"finn_kunde": ("Finner en kunde", True, lambda arguments: (None, None), schema)}
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", ["s"], ["u"], tools, None, None, [], 1024)
        self.assertEqual(len(body["tools"]), 1)
        self.assertEqual(body["tools"][0]["name"], "finn_kunde")
        self.assertEqual(body["tools"][0]["description"], "Finner en kunde")
        self.assertEqual(body["tools"][0]["input_schema"], schema)
        self.assertNotIn("tool_choice", body,
                         "Uten schema skal modellen selv velge om verktøy brukes")

    def test_strukturert_json_tvinger_sentinel_verktoeyet(self):
        """Anthropic har ikke output_config.format. Strukturert JSON løses ved å
        TVINGE et enkelt-verktøy. Blir tool_choice borte, får vi fritekst tilbake
        der kalleren venter JSON."""
        schema = {"type": "object", "properties": {"sum": {"type": "number"}}}
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", ["s"], ["u"], None, None, schema, [], 1024)
        self.assertEqual(body["tool_choice"], {"type": "tool", "name": "fiq_structured_response"})
        self.assertEqual(body["tools"][0]["input_schema"], schema)

    def test_schema_OG_verktoey_gir_instruksjon_ikke_tool_choice(self):
        """Kombinasjonen ville gitt verktøy-konflikt: da legges schemaet i system-
        teksten i stedet, og ekte verktøy beholdes."""
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        tools = {"ekte": ("Ekte verktøy", True, lambda arguments: (None, None), {"type": "object"})}
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", ["Basis."], ["u"], tools, None, schema, [], 1024)
        self.assertNotIn("tool_choice", body)
        self.assertEqual([t["name"] for t in body["tools"]], ["ekte"],
                         "Sentinel-verktøyet skal IKKE legges til når ekte verktøy finnes")
        self.assertIn("JSON matching this schema", body["system"])
        self.assertIn('"x"', body["system"])

    def test_akkumulerte_inputs_legges_etter_foerste_melding(self):
        """Verktøy-loopen bygger opp assistant(tool_use)/user(tool_result)-par.
        Rekkefølgen er kritisk — Anthropic avviser tool_result uten forutgående
        tool_use i samme samtale."""
        inputs = [
            {"role": "assistant", "content": [{"type": "tool_use", "id": "tu_1",
                                               "name": "f", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu_1",
                                          "content": "42"}]},
        ]
        body = ClaudeProvider.build_message_body(
            "claude-sonnet-5", ["s"], ["u"], None, None, None, inputs, 1024)
        self.assertEqual(len(body["messages"]), 3)
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertEqual(body["messages"][1]["role"], "assistant")
        self.assertEqual(body["messages"][2]["content"][0]["type"], "tool_result")

    def test_tool_result_bygges_paa_anthropic_form(self):
        """Odoos `_build_tool_call_response`-gren for anthropic."""
        r = ClaudeProvider.build_tool_result("tu_9", {"antall": 3})
        self.assertEqual(r["role"], "user")
        self.assertEqual(r["content"][0]["type"], "tool_result")
        self.assertEqual(r["content"][0]["tool_use_id"], "tu_9")
        self.assertEqual(r["content"][0]["content"], "{'antall': 3}",
                         "Anthropic krever streng i tool_result.content")

    # ---------- Tolking av svar ----------

    def test_tekstsvar_tolkes(self):
        response, to_call, next_inputs = ClaudeProvider.parse_message_response(SVAR_TEKST, [])
        self.assertEqual(response, ["Hei fra Claude."])
        self.assertEqual(to_call, [])
        self.assertEqual(next_inputs, [])

    def test_tomme_tekstblokker_forurenser_ikke_svaret(self):
        """En tom text-blokk skal ikke bli til et tomt svar-element."""
        svar = {"content": [{"type": "text", "text": ""},
                            {"type": "text", "text": "Ekte."}]}
        response, __, __ = ClaudeProvider.parse_message_response(svar, [])
        self.assertEqual(response, ["Ekte."])

    def test_tool_use_gir_kall_OG_ekko_av_assistentmeldingen(self):
        """🔴 Ekkoet av assistentens tool_use MÅ ligge i next_inputs. Mangler det,
        avviser Anthropic neste kall fordi tool_result ikke har noe å svare på."""
        svar = {"content": [
            {"type": "text", "text": "Jeg slår opp."},
            {"type": "tool_use", "id": "tu_7", "name": "finn_kunde", "input": {"navn": "Vidir"}},
        ]}
        response, to_call, next_inputs = ClaudeProvider.parse_message_response(svar, [])
        self.assertEqual(response, ["Jeg slår opp."])
        self.assertEqual(to_call, [("finn_kunde", "tu_7", {"navn": "Vidir"})])
        self.assertEqual(len(next_inputs), 1)
        self.assertEqual(next_inputs[-1]["role"], "assistant")
        blokktyper = [b["type"] for b in next_inputs[-1]["content"]]
        self.assertEqual(blokktyper, ["text", "tool_use"])

    def test_tidligere_inputs_bevares_og_muteres_ikke(self):
        """Loopen mater inn forrige runde. Muteres lista på plass, ødelegges historikken."""
        tidligere = [{"role": "user", "content": [{"type": "text", "text": "før"}]}]
        original = list(tidligere)
        svar = {"content": [{"type": "tool_use", "id": "t1", "name": "f", "input": {}}]}
        __, __, next_inputs = ClaudeProvider.parse_message_response(svar, tidligere)
        self.assertEqual(tidligere, original, "prior_inputs ble mutert på plass")
        self.assertEqual(len(next_inputs), 2)
        self.assertEqual(next_inputs[0], original[0])

    def test_uten_verktoeykall_ekkoes_ingen_assistentmelding(self):
        """Rent tekstsvar avslutter loopen — ekko ville lagt igjen søppel i historikken."""
        __, to_call, next_inputs = ClaudeProvider.parse_message_response(SVAR_TEKST, [])
        self.assertEqual(to_call, [])
        self.assertEqual(next_inputs, [])

    def test_sentinel_verktoeyet_blir_JSON_svar_ikke_verktoeykall(self):
        """🔴 Sentinelen er IKKE et ekte verktøy. Behandles den som et kall, går
        loopen i evig runde og prøver å kjøre et verktøy som ikke finnes."""
        svar = {"content": [{"type": "tool_use", "id": "tu_s",
                             "name": "fiq_structured_response",
                             "input": {"sum": 42}}]}
        response, to_call, next_inputs = ClaudeProvider.parse_message_response(svar, [])
        self.assertEqual(to_call, [], "Sentinelen skal ALDRI bli et verktøykall")
        self.assertEqual(json.loads(response[0]), {"sum": 42})
        self.assertEqual(next_inputs, [])

    def test_tomt_svar_kaster_ikke(self):
        """Et tomt/None-svar skal gi tomme lister, ikke AttributeError."""
        for tomt in (None, {}, {"content": None}, {"content": []}):
            response, to_call, next_inputs = ClaudeProvider.parse_message_response(tomt, [])
            self.assertEqual((response, to_call, next_inputs), ([], [], []),
                             "Tomt svar %r ga ikke tomme lister" % (tomt,))

    # ---------- FEILSTIEN ----------

    def test_api_feilsvar_gir_lesbar_ValueError(self):
        """Anthropic svarer 200 med {"type":"error"} i noen tilfeller. Da må vi
        kaste, ikke returnere et tomt svar som ser vellykket ut."""
        feil = {"type": "error", "error": {"type": "overloaded_error",
                                           "message": "Overloaded"}}
        with self.assertRaises(ValueError) as ctx:
            ClaudeProvider.parse_message_response(feil, [])
        self.assertIn("Overloaded", str(ctx.exception))

    def test_api_feilsvar_uten_melding_kaster_likevel(self):
        """Feil uten `message` skal fortsatt kaste — aldri stilltiende passere."""
        with self.assertRaises(ValueError):
            ClaudeProvider.parse_message_response({"type": "error"}, [])

    def test_feilmelding_lekker_ikke_noekkelen(self):
        """🔴 SIKKERHET: 401-svaret fra Anthropic kan ekko-e deler av forespørselen.
        Feilmeldingen vår må ALDRI inneholde nøkkelen."""
        feil = {"type": "error", "error": {"type": "authentication_error",
                                           "message": "invalid x-api-key"}}
        with self.assertRaises(ValueError) as ctx:
            ClaudeProvider.parse_message_response(feil, [])
        self.assertNotIn(TESTNOKKEL, str(ctx.exception))
        self.assertNotIn("sk-ant-api03", str(ctx.exception))


@tagged("post_install", "-at_install", "fiq_ai_claude")
class TestLLMApiServicePatch(TransactionCase):
    """Monkeypatchen mot Odoos `LLMApiService`. INGEN nettverk: `_request` mockes."""

    def setUp(self):
        super().setUp()
        self.icp = self.env["ir.config_parameter"].sudo()
        # OPPRETT vår egen tilstand — ikke stol på hva basen tilfeldigvis har.
        self.icp.set_param(ClaudeProvider.KEY_PARAM, TESTNOKKEL)
        self.addCleanup(self.icp.set_param, ClaudeProvider.KEY_PARAM, "")

    # ---------- Konstruksjon ----------

    def test_patchen_er_paa(self):
        self.assertTrue(getattr(LLMApiService, "_fiq_anthropic_patched", False),
                        "LLMApiService er ikke patchet — modulen er ikke lastet")

    def test_anthropic_gir_default_base_url(self):
        """Uten systemparam skal vi treffe api.anthropic.com/v1."""
        self.icp.set_param(ClaudeProvider.BASEURL_PARAM, "")
        svc = LLMApiService(self.env, provider="anthropic")
        self.assertEqual(svc.base_url, "https://api.anthropic.com/v1")
        self.assertEqual(svc.provider, "anthropic")

    def test_base_url_er_config_drevet(self):
        """Config-drevet: skal kunne flippes til FIQ-gateway UTEN kodeendring."""
        self.icp.set_param(ClaudeProvider.BASEURL_PARAM, "https://gateway.fiq.no/anthropic/v1/")
        self.addCleanup(self.icp.set_param, ClaudeProvider.BASEURL_PARAM, "")
        svc = LLMApiService(self.env, provider="anthropic")
        self.assertEqual(svc.base_url, "https://gateway.fiq.no/anthropic/v1",
                         "Etterfølgende «/» skal strippes — ellers blir ruta «//messages»")

    def test_openai_veien_er_urort(self):
        """🔴 REGRESJON: patchen skal utvide, ALDRI endre Odoos egne leverandører."""
        svc = LLMApiService(self.env, provider="openai")
        self.assertEqual(svc.base_url, "https://api.openai.com/v1")
        self.assertEqual(svc.provider, "openai")

    def test_ukjent_leverandoer_kaster_fortsatt(self):
        """Patchen må ikke svelge Odoos egen NotImplementedError for ukjente."""
        with self.assertRaises(NotImplementedError):
            LLMApiService(self.env, provider="finnes-ikke")

    # ---------- Nøkkelhåndtering: SIKKERHET ----------

    def test_noekkel_hentes_fra_systemparameter(self):
        svc = LLMApiService(self.env, provider="anthropic")
        self.assertEqual(svc._get_api_token(), TESTNOKKEL)

    def test_uten_noekkel_kastes_UserError_UTEN_noekkelinnhold(self):
        """🔴 SIKKERHET + brukbarhet: feilen skal si HVILKEN systemparam som mangler,
        og ikke noe mer. Aldri en delvis nøkkel, aldri en env-verdi."""
        self.icp.set_param(ClaudeProvider.KEY_PARAM, "")
        with patch.dict("os.environ", {}, clear=False) as miljo:
            miljo.pop("ANTHROPIC_API_KEY", None)
            svc = LLMApiService(self.env, provider="anthropic")
            with self.assertRaises(UserError) as ctx:
                svc._get_api_token()
        melding = str(ctx.exception)
        self.assertIn(ClaudeProvider.KEY_PARAM, melding)
        self.assertNotIn("sk-ant", melding)

    def test_noekkelen_logges_ALDRI(self):
        """🔴 SIKKERHETSTEST: hele kallet kjøres med logging fanget. Havner nøkkelen
        i en eneste logglinje, ligger den i klartekst i Odoo.sh-loggene for alltid."""
        svc = LLMApiService(self.env, provider="anthropic")
        with patch.object(LLMApiService, "_request", return_value=SVAR_TEKST):
            with self.assertLogs("odoo.addons.fiq_ai_claude", level="DEBUG") as logg:
                svc._request_llm("claude-sonnet-5", ["system"], ["spørsmål"])
        alt = "\n".join(logg.output)
        self.assertNotIn(TESTNOKKEL, alt, "API-NØKKELEN BLE LOGGET")
        self.assertNotIn("sk-ant", alt, "Noe nøkkel-lignende ble logget")
        self.assertNotIn("x-api-key", alt, "Header-navnet med nøkkel ble logget")

    def test_noekkelen_returneres_ikke_til_kalleren(self):
        """🔴 SIKKERHET: svaret som når brukerflaten skal ikke inneholde nøkkelen."""
        svc = LLMApiService(self.env, provider="anthropic")
        with patch.object(LLMApiService, "_request", return_value=SVAR_TEKST):
            response, to_call, next_inputs = svc._request_llm(
                "claude-sonnet-5", ["s"], ["u"])
        raa = json.dumps([response, to_call, next_inputs], default=str)
        self.assertNotIn(TESTNOKKEL, raa)
        self.assertNotIn("sk-ant", raa)

    # ---------- Ruting ----------

    def test_anthropic_ruter_til_messages_IKKE_responses(self):
        """🔴 KJERNEN i modulen. Anthropic har INGEN /responses-endepunkt — treffer
        vi OpenAIs rute, feiler hvert eneste kall med 404."""
        svc = LLMApiService(self.env, provider="anthropic")
        with patch.object(LLMApiService, "_request", return_value=SVAR_TEKST) as mock_req:
            svc._request_llm("claude-sonnet-5", ["system"], ["spørsmål"])
        self.assertEqual(mock_req.call_count, 1)
        kwargs = mock_req.call_args.kwargs
        self.assertEqual(kwargs["endpoint"], "/messages")
        self.assertEqual(kwargs["method"], "post")
        self.assertEqual(kwargs["headers"]["x-api-key"], TESTNOKKEL)
        self.assertEqual(kwargs["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(kwargs["body"]["model"], "claude-sonnet-5")
        self.assertNotIn("input", kwargs["body"],
                         "«input» er OpenAI-formen — Anthropic bruker «messages»")

    def test_max_tokens_hentes_fra_systemparameter(self):
        """Config-drevet grense. Uten den brukes DEFAULT_MAX_TOKENS."""
        self.icp.set_param(ClaudeProvider.MAXTOKENS_PARAM, "512")
        self.addCleanup(self.icp.set_param, ClaudeProvider.MAXTOKENS_PARAM, "")
        svc = LLMApiService(self.env, provider="anthropic")
        with patch.object(LLMApiService, "_request", return_value=SVAR_TEKST) as mock_req:
            svc._request_llm("claude-sonnet-5", ["s"], ["u"])
        self.assertEqual(mock_req.call_args.kwargs["body"]["max_tokens"], 512)

    def test_ugyldig_max_tokens_faller_tilbake_uten_aa_kaste(self):
        """🔴 FEILSTI: en menneskeskrevet systemparam kan inneholde hva som helst.
        «mange» skal gi default, ikke ValueError midt i et brukerkall."""
        self.icp.set_param(ClaudeProvider.MAXTOKENS_PARAM, "mange")
        self.addCleanup(self.icp.set_param, ClaudeProvider.MAXTOKENS_PARAM, "")
        svc = LLMApiService(self.env, provider="anthropic")
        with patch.object(LLMApiService, "_request", return_value=SVAR_TEKST) as mock_req:
            svc._request_llm("claude-sonnet-5", ["s"], ["u"])
        self.assertEqual(mock_req.call_args.kwargs["body"]["max_tokens"],
                         ClaudeProvider.DEFAULT_MAX_TOKENS)

    def test_tool_call_response_ruter_paa_leverandoer(self):
        """Samme metode, to former. Feil form = Anthropic avviser hele samtalen."""
        anth = LLMApiService(self.env, provider="anthropic")
        self.assertEqual(anth._build_tool_call_response("t1", "svar")["role"], "user")
        oai = LLMApiService(self.env, provider="openai")
        self.assertEqual(oai._build_tool_call_response("t1", "svar")["type"],
                         "function_call_output")

    # ---------- FEILSTIEN gjennom hele stakken ----------

    def test_timeout_boblet_opp_som_UserError(self):
        """🔴 FEILSTI: nettet henger. Odoos `_request` gjør requests-feil om til
        UserError. Vi skal ikke svelge den — kalleren må få vite at det feilet."""
        svc = LLMApiService(self.env, provider="anthropic")
        with patch.object(LLMApiService, "_request",
                          side_effect=UserError("Timeout mot Anthropic")):
            with self.assertRaises(UserError):
                svc._request_llm("claude-sonnet-5", ["s"], ["u"])

    def test_raa_requests_timeout_boblet_opp(self):
        """Samme, men med den rå requests-feilen — ingen stilltiende None-retur."""
        svc = LLMApiService(self.env, provider="anthropic")
        with patch.object(LLMApiService, "_request",
                          side_effect=requests.exceptions.ConnectTimeout("tidsavbrudd")):
            with self.assertRaises(requests.exceptions.RequestException):
                svc._request_llm("claude-sonnet-5", ["s"], ["u"])

    def test_http_feil_gir_ikke_falskt_tomt_svar(self):
        """🔴 En 401/429 må ALDRI ende som «(tomt svar)» — da tror brukeren at
        Claude svarte, mens nøkkelen egentlig er utløpt."""
        svc = LLMApiService(self.env, provider="anthropic")
        with patch.object(LLMApiService, "_request",
                          side_effect=UserError("401 authentication_error")):
            with self.assertRaises(UserError):
                svc._request_llm("claude-sonnet-5", ["s"], ["u"])

    def test_ugyldig_json_kropp_gir_feil_ikke_falskt_svar(self):
        """FEILSTI: en gateway kan returnere en liste eller en streng i stedet for
        et objekt. Da MÅ vi feile — et søppel-svar som stille blir til «ingen
        respons» ser vellykket ut for kalleren.

        MERK (dokumentert oppførsel, verifisert i kjøring): `parse_message_response`
        kaller `.get()` på svaret, så en liste/streng gir AttributeError. Det er
        akseptabelt — det er en feil, ikke et falskt tomt svar. Odoos egen
        `assertRaises` tar KUN én unntaksklasse (ikke tuple), så vi fanger bredt
        med try/except i stedet."""
        svc = LLMApiService(self.env, provider="anthropic")
        for soppel in (["ikke", "et", "objekt"], "ren streng", 42):
            with patch.object(LLMApiService, "_request", return_value=soppel):
                with self.assertRaises(Exception,
                                       msg="Søppel-svar %r ga ingen feil" % (soppel,)):
                    svc._request_llm("claude-sonnet-5", ["s"], ["u"])

    def test_anthropic_feilsvar_gjennom_hele_stakken(self):
        """End-to-end feilsti: mocket HTTP-svar med error-form → ValueError."""
        svc = LLMApiService(self.env, provider="anthropic")
        feil = {"type": "error", "error": {"type": "rate_limit_error",
                                           "message": "Rate limit"}}
        with patch.object(LLMApiService, "_request", return_value=feil):
            with self.assertRaises(ValueError) as ctx:
                svc._request_llm("claude-sonnet-5", ["s"], ["u"])
        self.assertIn("Rate limit", str(ctx.exception))
