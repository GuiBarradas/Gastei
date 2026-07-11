"""GeminiLLMClient — adapter over ``google-genai`` (free tier supported).

Implements the ``LLMClient`` port by translating between the Anthropic-shaped
messages the domain produces and Gemini's own ``contents`` / ``parts`` /
``function_call`` model.

Key translations:

- ``system`` → ``system_instruction``
- ``{role: 'user', content: str}``                  → ``Content(role='user', parts=[Part(text=...)])``
- ``{role: 'assistant', content: [text|tool_use]}`` → ``Content(role='model', parts=[text|function_call])``
- ``{role: 'user', content: [tool_result]}``        → ``Content(role='user', parts=[function_response])``
- Gemini ``function_call`` (no native id)           → ``LLMToolUse(id=synthesized UUID)``
"""

from __future__ import annotations

import uuid
from typing import Any

from google import genai
from google.genai import types

from gastei.config import get_settings
from gastei.schemas.llm import LLMResponse, LLMToolUse


class GeminiLLMClient:
    # A hung call must not stall callers that fan out over many batches.
    REQUEST_TIMEOUT_MS = 30_000

    def __init__(self, api_key: str | None = None) -> None:
        self._client = genai.Client(
            api_key=api_key or get_settings().google_api_key or None,
            http_options=types.HttpOptions(timeout=self.REQUEST_TIMEOUT_MS),
        )

    async def messages_create(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        contents = self._translate_messages(messages)
        config_kwargs: dict[str, Any] = {
            "system_instruction": system,
            "max_output_tokens": max_tokens,
        }
        if tools:
            config_kwargs["tools"] = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t["name"],
                            description=t["description"],
                            parameters=t["input_schema"],
                        )
                        for t in tools
                    ]
                )
            ]

        response = await self._client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )

        return self._translate_response(response)

    # ------------------------------------------------------------------
    # Message translation (Anthropic-shaped → Gemini)
    # ------------------------------------------------------------------

    def _translate_messages(self, messages: list[dict[str, Any]]) -> list[types.Content]:
        contents: list[types.Content] = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "user" and isinstance(content, str):
                contents.append(types.Content(role="user", parts=[types.Part(text=content)]))
                continue

            if role == "user" and isinstance(content, list):
                parts: list[types.Part] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        name = self._find_tool_name(messages, block.get("tool_use_id"))
                        result_value = block.get("content", "")
                        parts.append(
                            types.Part.from_function_response(
                                name=name,
                                response={"result": str(result_value)},
                            )
                        )
                    elif block.get("type") == "text":
                        parts.append(types.Part(text=block["text"]))
                if parts:
                    contents.append(types.Content(role="user", parts=parts))
                continue

            if role == "assistant":
                parts = []
                if isinstance(content, str):
                    parts.append(types.Part(text=content))
                elif isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "text":
                            parts.append(types.Part(text=block["text"]))
                        elif block.get("type") == "tool_use":
                            parts.append(
                                types.Part(
                                    function_call=types.FunctionCall(
                                        name=block["name"],
                                        args=block.get("input", {}),
                                    )
                                )
                            )
                if parts:
                    contents.append(types.Content(role="model", parts=parts))

        return contents

    @staticmethod
    def _find_tool_name(messages: list[dict[str, Any]], tool_use_id: str | None) -> str:
        if not tool_use_id:
            return "unknown_tool"
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("id") == tool_use_id
                ):
                    return block.get("name", "unknown_tool")
        return "unknown_tool"

    # ------------------------------------------------------------------
    # Response translation (Gemini → LLMResponse)
    # ------------------------------------------------------------------

    @staticmethod
    def _translate_response(
        response: types.GenerateContentResponse,
    ) -> LLMResponse:
        if not response.candidates:
            return LLMResponse(stop_reason="end_turn", text="")

        candidate = response.candidates[0]
        text_parts: list[str] = []
        tool_uses: list[LLMToolUse] = []
        raw_content: list[dict[str, Any]] = []

        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                    raw_content.append({"type": "text", "text": part.text})
                elif getattr(part, "function_call", None):
                    fc = part.function_call
                    synthetic_id = f"tu_{uuid.uuid4().hex[:16]}"
                    args = dict(fc.args) if fc.args else {}
                    tool_uses.append(LLMToolUse(id=synthetic_id, name=fc.name, input=args))
                    raw_content.append(
                        {
                            "type": "tool_use",
                            "id": synthetic_id,
                            "name": fc.name,
                            "input": args,
                        }
                    )

        if tool_uses:
            stop_reason: str = "tool_use"
        else:
            finish = getattr(candidate, "finish_reason", None)
            finish_name = getattr(finish, "name", str(finish) if finish else "")
            if finish_name == "MAX_TOKENS":
                stop_reason = "max_tokens"
            elif finish_name == "STOP":
                stop_reason = "end_turn"
            else:
                stop_reason = "end_turn"

        usage = getattr(response, "usage_metadata", None)
        return LLMResponse(
            text="".join(text_parts),
            stop_reason=stop_reason,
            tool_uses=tool_uses,
            raw_content=raw_content,
            tokens_input=getattr(usage, "prompt_token_count", 0) or 0,
            tokens_output=getattr(usage, "candidates_token_count", 0) or 0,
        )
