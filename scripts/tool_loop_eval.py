"""How well the assistant chooses tools, on the real model, against fixed tools.

Usage:
    python scripts/tool_loop_eval.py [--voice]

Each case is a turn (typed, or with --voice spoken through the streaming
path with silent speech) to an assistant whose stores are isolated
(scripts/turn_eval.py) and which has one MCP server, scripts/
tool_eval_server.py, with fixed answers. Reported per case:

    tools     the calls that reached the server, in order
    right     the expected tools and only those were called
    extra     calls beyond the expected ones (an unnecessary call is a
              failure of judgement, not a success)
    bad args  calls refused for their arguments
    repeats   the loop stopped a repeated call
    answer    the reply holds what it must and nothing it must not
    seconds   the whole turn

The cases cover a question needing no tool, one tool, two tools in turn,
two plausible tools, an answer already in memory, an answer in the owner's
documents, a refused (unoffered) tool, a change that needs the owner's yes,
and a request too vague to act on.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


@dataclass
class Case:
    name: str
    said: str
    tools: list[str]
    must: list[str] = field(default_factory=list)
    must_not: list[str] = field(default_factory=list)
    before: list[str] = field(default_factory=list)
    then: str | None = None


CASES = [
    Case("no tool needed", "What is 17 times 23?", [], must=["391"]),
    Case("one tool", "What's the weather in Delhi right now?", ["get_weather"], must=["31"]),
    Case("two tools in turn", "When does my Goa flight leave?", ["find_booking", "flight_status"], must=["7:40"]),
    Case("two tools, time asked", "What time does my Goa flight take off?", ["find_booking", "flight_status"],
         must=["7:40"]),
    Case("two plausible tools", "Will it keep raining in Mumbai over the next few days?", ["get_forecast"], must=["rain"]),
    Case("memory has it", "What's my locker code?", [], must=["7314"],
         before=["Please remember that my gym locker code is 7314."]),
    Case("document has it", "How much notice do I have to give my landlord?", [], must=["two months"]),
    Case("external data needed", "How's the weather in London today?", ["get_weather"], must=["12"]),
    Case("tool not offered", "Delete every event in my calendar.", [], must_not=["cleared", "deleted all", "done"]),
    Case("change needs a yes", "Put a dentist appointment on my calendar for Friday at 5 pm.", ["add_calendar_event"],
         must=["couldn't confirm"], then="yes"),
    Case("too vague to act on", "What's the weather?", [], must=["?"]),
]


async def run(voice: bool) -> int:
    import turn_eval

    from Agent_Guru.integration.mcp_tools import (
        ServerConfig,
        ToolRisk,
        ToolRule,
        install_mcp_policies,
    )
    from Agent_Guru.platform.features.documents import DocumentStore

    folder = Path(tempfile.mkdtemp(prefix="tool_eval_"))
    log = folder / "calls.jsonl"
    rules = {name: ToolRule(allow=True, risk=ToolRisk.READ_ONLY)
             for name in ("get_weather", "get_forecast", "find_booking", "flight_status")}
    rules["add_calendar_event"] = ToolRule(allow=True, risk=ToolRisk.EXTERNAL_SIDE_EFFECT)
    rules["clear_calendar"] = ToolRule(allow=False, risk=ToolRisk.DESTRUCTIVE)
    servers = [ServerConfig(
        name="eval", command=sys.executable, args=[str(Path(__file__).with_name("tool_eval_server.py"))],
        env={"TOOL_EVAL_LOG": str(log)}, timeout=10.0, tools=rules,
    )]
    harness = turn_eval.Harness()
    await harness.start()
    install_mcp_policies(harness.policy, servers)
    lease = folder / "lease.txt"
    lease.write_text("Notice period. Either party may end this agreement by giving two months' written notice.",
                     encoding="utf-8")
    documents = DocumentStore(folder / "documents.db")
    await documents.add(lease)

    from Agent_Guru.memory.memory_manager import MemoryManager

    rows = []
    for case in CASES:
        # A fresh memory per case, held in this process only: with one
        # memory for the whole run, a case was answered from an earlier
        # case's answer ("asking about Delhi again? It's 31 C") without the
        # tool, and the next run in the same process from the last run's.
        harness.memory = MemoryManager(platform_override="eval")
        orch = harness.session()
        orch._mcp_servers = servers
        orch._documents = documents
        orch._start_tools()
        await orch._tools_starting

        async def turn(text: str, orch=orch):
            if voice:
                result, _ = await harness.say(orch, text)
                return result
            return await orch.run_text_turn(text)

        for line in case.before:
            await turn(line)
        log.write_text("", encoding="utf-8")
        started = time.perf_counter()
        result = await turn(case.said)
        stages = list(result.tool_stages)
        reply = result.llm_response or result.action_result or ""
        if case.then and orch._tool_pending is not None:
            asked = reply
            result = await turn(case.then)
            stages += result.tool_stages
            reply = f"{asked} / {result.llm_response or result.action_result or ''}"
        seconds = time.perf_counter() - started
        await orch.close_tools()
        called = [json.loads(line)["tool"] for line in log.read_text(encoding="utf-8").splitlines() if line]
        bad = sum(1 for s in stages if s.name == "mcp_call" and s.detail.get("category") == "bad_arguments")
        repeats = sum(1 for s in stages if s.name == "tool_loop" and s.detail.get("stop") == "repeat")
        right = called == case.tools
        extra = max(0, len(called) - len(case.tools)) if set(case.tools) <= set(called) else len(set(called) - set(case.tools))
        lowered = reply.lower()
        answer_ok = all(m.lower() in lowered for m in case.must) and not any(m.lower() in lowered for m in case.must_not)
        rows.append((case, called, right, extra, bad, repeats, answer_ok, seconds, reply))
        print(f"{'ok  ' if right and answer_ok else 'MISS'} {case.name:22} tools={called} extra={extra} "
              f"bad_args={bad} repeats={repeats} answer={'ok' if answer_ok else 'WRONG'} {seconds:5.1f}s  {reply[:150]!r}")

    await harness.memory.shutdown()
    picked = sum(r[2] for r in rows)
    answered = sum(r[6] for r in rows)
    print(f"\ntools right {picked}/{len(rows)}, answers right {answered}/{len(rows)}, "
          f"unnecessary calls {sum(r[3] for r in rows)}, bad arguments {sum(r[4] for r in rows)}, "
          f"repeats stopped {sum(r[5] for r in rows)}, median turn {sorted(r[7] for r in rows)[len(rows) // 2]:.1f}s")
    return 0 if picked == answered == len(rows) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--voice", action="store_true", help="speak each turn through the streaming path (silent speech)")
    sys.exit(asyncio.run(run(parser.parse_args().voice)))
