"""One fixed model and Portkey route for every production agent."""

import os
import json
from math import ceil
import tiktoken
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from .models import RunBudget
from pydantic_ai.usage import RequestUsage

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent.parent
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"


def load_environment():
    for folder in (ROOT, WORKSPACE):
        load_dotenv(folder / ".env", override=False)


def budget_from_environment() -> RunBudget:
    load_environment()
    values = {}
    for name in RunBudget.model_fields:
        value = os.getenv("CAMPUS_" + name.upper())
        if value is not None and value.strip():
            values[name] = value
    return RunBudget(**values)


class PortkeyResponsesModel(OpenAIResponsesModel):
    async def count_tokens(self, messages, model_settings, model_request_parameters):
        """Local conservative estimate; managed Azure routes lack /responses/input_tokens."""
        settings, parameters = self.prepare_request(model_settings, model_request_parameters)
        request = await self._build_responses_request_params(messages, settings or {}, parameters, self.profile)
        payload = json.dumps({'input':request.input, 'instructions':request.instructions,
                              'tools':request.tools, 'text':request.text}, ensure_ascii=False, default=str)
        estimate = ceil(len(tiktoken.get_encoding('o200k_base').encode(payload, disallowed_special=())) * 1.25) + 256
        return RequestUsage(input_tokens=estimate)


def build_model():
    load_environment()
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing; configure the environment or ignored .env.")
    client = AsyncOpenAI(api_key=key, base_url=PORTKEY_BASE_URL, max_retries=0,
                         default_headers={"x-portkey-api-key": key, "x-portkey-provider": "openai"})
    return PortkeyResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
