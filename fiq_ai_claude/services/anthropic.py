# Part of FIQ. See LICENSE file for full copyright and licensing details.
"""
Portabel Claude/Anthropic-leverandørlogikk.

Denne klassen er bevisst skrevet som en frittstående «provider + api-service» enhet slik at
den speiler Odoo 20s `ai/services/`-arkitektur (AIProvider + AIApiService). På Odoo 19 wires
den inn i den eksisterende `ai.utils.llm_api_service.LLMApiService` via monkeypatch
(se `models/ai_patch.py`). Ved port til Odoo 20 blir dette to subklasser
(`AIProviderAnthropic(AIProvider)` + `AIApiServiceAnthropic(AIApiService)`) uten omskriving
av selve oversettingen mot Messages API.

KJERNEFAKTA:
- Anthropic har ingen Responses-API. Odoos openai-vei poster til `/responses`; vi poster til
  `/v1/messages` (Messages API) med headere x-api-key + anthropic-version.
- Anthropic har INGEN embeddings og INGEN transkripsjon → de forblir OpenAI/Google.
- `max_tokens` er PÅKREVD av Anthropic. `temperature` sendes IKKE (avvises på Opus 4.8 / Sonnet 5).
"""
import json

# --- Sentinel for strukturert JSON-utdata (Anthropic har ikke output_config.format) ---
_STRUCTURED_TOOL = "fiq_structured_response"


class ClaudeProvider:
    # ---- Identitet (speiler v20 AIProvider-attributter) ----
    NAME = "anthropic"
    DISPLAY_NAME = "Anthropic (Claude)"
    API_URL = "https://api.anthropic.com/v1"
    KEY_PARAM = "ai.anthropic_key"           # system-param som holder API-nøkkelen
    BASEURL_PARAM = "ai.anthropic_base_url"  # config-drevet: flippes til FIQ-gateway senere
    MAXTOKENS_PARAM = "ai.anthropic_max_tokens"
    ANTHROPIC_VERSION = "2023-06-01"
    DEFAULT_MAX_TOKENS = 8192

    # Anthropic mangler embeddings → tom modell (forurenser ikke EMBEDDING_MODELS_SELECTION,
    # som bygges ved import FØR vi appender). Ingen embedding-/transkripsjonsmodeller.
    EMBEDDING_MODEL = ""
    EMBEDDING_CONFIG = {}

    # ---- LLM-modeller (v20-navn get_llm_models) ----
    LLMS = [
        ("claude-opus-4-8", "Claude Opus 4.8"),
        ("claude-sonnet-5", "Claude Sonnet 5"),
        ("claude-haiku-4-5", "Claude Haiku 4.5"),
    ]

    # Response-stil → (modell). Speiler v20 get_llm_model_config-mønster.
    LLM_MODEL_CONFIG = {
        "standard": "claude-sonnet-5",
        "nuanced": "claude-sonnet-5",
        "snappy_and_creative": "claude-haiku-4-5",
        "slow_and_rigorous": "claude-opus-4-8",
    }

    # ---------- v20-kompatible klassemetoder ----------
    @classmethod
    def get_llm_models(cls):
        return list(cls.LLMS)

    @classmethod
    def get_embedding_model(cls):
        return cls.EMBEDDING_MODEL

    @classmethod
    def get_transcription_models(cls):
        return []

    @classmethod
    def get_llm_model(cls, response_style):
        return cls.LLM_MODEL_CONFIG.get(response_style, "claude-sonnet-5")

    # ---------- HTTP-bygging ----------
    @classmethod
    def build_headers(cls, api_key):
        return {
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": cls.ANTHROPIC_VERSION,
        }

    @staticmethod
    def _build_user_content(user_prompts, files):
        content = []
        for prompt in (user_prompts or []):
            if prompt:
                content.append({"type": "text", "text": prompt})
        for f in (files or []):
            mimetype = f.get("mimetype", "")
            value = f.get("value")
            if mimetype == "text/plain":
                content.append({"type": "text", "text": value})
            elif mimetype.startswith("image/"):
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": mimetype, "data": value},
                })
            elif mimetype == "application/pdf":
                content.append({
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": value},
                })
            else:
                content.append({"type": "text", "text": str(value)})
        if not content:
            content = [{"type": "text", "text": ""}]
        return content

    @staticmethod
    def _build_tools(tools):
        """Odoos tools-dict: {name: (description, allow_end_message, callable, parameter_schema)}
        → Anthropic tool-defs. Merk: Odoo har allerede injisert `__end_message` i schema."""
        anth_tools = []
        for name, spec in (tools or {}).items():
            description = spec[0]
            parameter_schema = spec[3]
            anth_tools.append({
                "name": name,
                "description": description,
                "input_schema": parameter_schema,
            })
        return anth_tools

    @classmethod
    def build_message_body(cls, model, system_prompts, user_prompts, tools, files, schema, inputs, max_tokens):
        messages = [{"role": "user", "content": cls._build_user_content(user_prompts, files)}]
        # `inputs` = akkumulerte assistant(tool_use) / user(tool_result)-meldinger fra loopen.
        messages.extend(inputs or [])

        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        system = "\n\n".join(p for p in (system_prompts or []) if p)

        anth_tools = cls._build_tools(tools)
        if schema and not tools:
            # Strukturert JSON: tving et enkelt-verktøy og les inputen som svaret.
            anth_tools.append({
                "name": _STRUCTURED_TOOL,
                "description": "Return the final answer strictly matching the given JSON schema.",
                "input_schema": schema,
            })
            body["tool_choice"] = {"type": "tool", "name": _STRUCTURED_TOOL}
        elif schema and tools:
            # Kombinert: legg schema som instruksjon (mykere, men unngår tool-konflikt).
            system = (system + "\n\nWhen giving the final answer, respond with JSON matching this schema: "
                      + json.dumps(schema)).strip()

        if system:
            body["system"] = system
        if anth_tools:
            body["tools"] = anth_tools
        return body

    @staticmethod
    def build_tool_result(tool_call_id, return_value):
        """Anthropic-gren for LLMApiService._build_tool_call_response."""
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": str(return_value),
            }],
        }

    @staticmethod
    def parse_message_response(llm_response, prior_inputs):
        """Anthropic Messages-svar → Odoos (response, to_call, next_inputs)-kontrakt.
        - text-blokker → response
        - tool_use-blokker → to_call [(name, id, arguments)] + ekko av assistant-meldingen i inputs
        - sentinel-verktøyet (strukturert JSON) → svaret som JSON-tekst, IKKE et tool-kall
        """
        if isinstance(llm_response, dict) and llm_response.get("type") == "error":
            err = llm_response.get("error") or {}
            msg = err.get("message") or json.dumps(llm_response)
            raise ValueError("Anthropic API error: %s" % msg)

        content = (llm_response or {}).get("content") or []
        response, to_call, assistant_blocks = [], [], []
        for block in content:
            btype = block.get("type")
            if btype == "text":
                text = block.get("text", "")
                assistant_blocks.append({"type": "text", "text": text})
                if text:
                    response.append(text)
            elif btype == "tool_use":
                name = block.get("name", "")
                if name == _STRUCTURED_TOOL:
                    # Terminal strukturert svar — returner som JSON-tekst.
                    response.append(json.dumps(block.get("input") or {}))
                    continue
                assistant_blocks.append(block)  # ekko rå tool_use-blokk
                to_call.append((name, block.get("id"), block.get("input") or {}))

        next_inputs = list(prior_inputs or [])
        if assistant_blocks and to_call:
            # Ekko av assistentens tool_use MÅ ligge før tool_result i neste kall.
            next_inputs.append({"role": "assistant", "content": assistant_blocks})

        return response, to_call, next_inputs
