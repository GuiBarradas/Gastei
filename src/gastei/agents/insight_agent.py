"""InsightAgent — chat with tool use (ARCHITECTURE.md §7.3).

Loop: call the LLM. On ``end_turn``, return; on ``tool_use``, execute the
requested tools and feed their results back as ``tool_result`` blocks;
repeat up to ``max_iterations`` (default 8). Unknown tools or tools that
raise become ``tool_result`` blocks with ``is_error=True`` — the model
can recover by switching to a different strategy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from gastei.agents.tools import AgentTool
from gastei.domain.ports import LLMClient
from gastei.schemas.llm import LLMToolUse

logger = logging.getLogger(__name__)


# The system prompt is in Portuguese because the agent talks to a Brazilian
# user (currency, date format, taxonomy labels). Translating the prompt
# would degrade output quality without changing the user-visible language.
SYSTEM_PROMPT = """Você é o Gastei, assistente financeiro pessoal do usuário.

CONTEXTO:
- Você tem acesso aos dados financeiros do usuário através de tools.
- TODA afirmação numérica DEVE vir de uma tool call. Nunca invente valores.
- Seja direto e prático. O usuário quer insights acionáveis, não relatórios longos.
- Use BRL como moeda. Datas em formato BR (DD/MM/YYYY) ao apresentar; nas tools, use ISO (YYYY-MM-DD).
- Seja honesto sobre limitações: se faltar dado, peça pra sincronizar.

ESTILO:
- Tom amigável mas objetivo. Sem floreio.
- Quando apresentar números, contextualize quando possível.
- Sugestões devem ser específicas e priorizadas.

CUIDADO:
- Nunca dê "conselho de investimento" no sentido regulado. Você comenta dados, não recomenda ativos.
- Para dívidas, foque em fatos: taxa, prazo, impacto no fluxo. Sugestões são opções, não ordens.
"""


class AgentTimeoutError(Exception):
    """The loop reached ``max_iterations`` without an ``end_turn``."""


@dataclass
class AgentResponse:
    text: str
    iterations: int
    messages: list[dict[str, Any]] = field(default_factory=list)
    tokens_input: int = 0
    tokens_output: int = 0


class InsightAgent:
    def __init__(
        self,
        llm: LLMClient,
        tools: list[AgentTool],
        model: str,
        max_iterations: int = 8,
        max_tokens: int = 4096,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        self._llm = llm
        self._tools_by_name = {t.name: t for t in tools}
        self._tool_schemas = [t.schema for t in tools]
        self._model = model
        self._max_iterations = max_iterations
        self._max_tokens = max_tokens
        self._system = system_prompt

    async def run(
        self,
        user_message: str,
        history: list[dict[str, Any]] | None = None,
    ) -> AgentResponse:
        messages: list[dict[str, Any]] = list(history or [])
        messages.append({"role": "user", "content": user_message})

        total_in = 0
        total_out = 0

        for iteration in range(1, self._max_iterations + 1):
            response = await self._llm.messages_create(
                model=self._model,
                system=self._system,
                messages=messages,
                tools=self._tool_schemas,
                max_tokens=self._max_tokens,
            )
            total_in += response.tokens_input
            total_out += response.tokens_output

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.raw_content})
                tool_results = await self._execute_tools(response.tool_uses)
                messages.append({"role": "user", "content": tool_results})
                continue

            # end_turn, max_tokens, stop_sequence — all terminate the loop.
            return AgentResponse(
                text=response.text,
                iterations=iteration,
                messages=[
                    *messages,
                    {"role": "assistant", "content": response.raw_content or response.text},
                ],
                tokens_input=total_in,
                tokens_output=total_out,
            )

        raise AgentTimeoutError(
            f"Reached max_iterations={self._max_iterations} without an end_turn. "
            "The LLM is most likely stuck in a tool-use loop."
        )

    async def _execute_tools(self, tool_uses: list[LLMToolUse]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for tu in tool_uses:
            block = await self._dispatch(tu)
            results.append(block)
        return results

    async def _dispatch(self, tu: LLMToolUse) -> dict[str, Any]:
        tool = self._tools_by_name.get(tu.name)
        if tool is None:
            return {
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": (
                    f"Error: tool {tu.name!r} does not exist. "
                    f"Available tools: {sorted(self._tools_by_name)}"
                ),
                "is_error": True,
            }
        try:
            output = await tool.execute(tu.input)
            return {
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": output,
            }
        except Exception as exc:
            logger.exception("Tool %s failed", tu.name)
            return {
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": f"Error running {tu.name}: {exc}",
                "is_error": True,
            }
