"""GeminiLLMClient translation specs — no network.

Gemini 3.x rejects replayed histories whose function calls lack the
``thought_signature`` the model originally returned. The adapter must carry
it through ``raw_content`` (base64) and echo it back on the next turn.
"""

from __future__ import annotations

import base64

import pytest
from google.genai import types

from gastei.clients.gemini_client import GeminiLLMClient

pytestmark = pytest.mark.unit

SIG = b"opaque-signature-bytes"


def _response_with_function_call() -> types.GenerateContentResponse:
    part = types.Part(
        function_call=types.FunctionCall(name="get_spending_by_category", args={"top_n": 5}),
        thought_signature=SIG,
    )
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[part]))]
    )


def test_thought_signature_survives_response_translation() -> None:
    result = GeminiLLMClient._translate_response(_response_with_function_call())

    assert result.stop_reason == "tool_use"
    block = result.raw_content[0]
    assert block["type"] == "tool_use"
    assert base64.b64decode(block["thought_signature"]) == SIG


def test_thought_signature_echoed_back_on_replay() -> None:
    client = GeminiLLMClient(api_key="fake")
    result = GeminiLLMClient._translate_response(_response_with_function_call())

    contents = client._translate_messages(
        [
            {"role": "user", "content": "quanto gastei?"},
            {"role": "assistant", "content": result.raw_content},
        ]
    )

    fc_part = contents[1].parts[0]
    assert fc_part.function_call.name == "get_spending_by_category"
    assert fc_part.thought_signature == SIG


def test_function_call_without_signature_still_replays() -> None:
    client = GeminiLLMClient(api_key="fake")
    contents = client._translate_messages(
        [
            {"role": "user", "content": "oi"},
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}],
            },
        ]
    )
    assert contents[1].parts[0].thought_signature is None
