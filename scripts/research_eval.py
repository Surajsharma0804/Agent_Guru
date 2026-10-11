"""Research on the real model and the real web: does each answer cite what its tools found?

Usage:
    python scripts/research_eval.py [--voice]

Each case is a typed turn (or with --voice, spoken through the streaming
path with silent speech) to an assistant whose stores are isolated
(scripts/turn_eval.py), with the research tools of integration/research.py
and nothing else. Needs the internet; the answers depend on what the web
says on the day, so the checks are about the sources, not exact wording:

    tools      the research tools the turn called
    cited      the source ids the answer cites, all of them returned by its tools
    removed    citations or URLs the check removed (invented by the model)
    unmatched  cited sentences holding a number the sources do not hold
    expect     the answer holds the expected word, when one is given
    seconds    the whole turn
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


@dataclass
class Case:
    name: str
    said: str
    #: True: must research; False: must not; None: either, if right.
    research: bool | None
    expect: str | None = None
    #: The providers may have nothing current (Wikipedia has no news): the
    #: answer must then say so rather than cite; invented sources still fail.
    may_lack_sources: bool = False


CASES = [
    Case("no research needed", "What is 12 times 12?", False, "144"),
    Case("current office holder", "Who is the current prime minister of India?", True, "modi"),
    Case("hardware fact", "How much video memory does the Nvidia GeForce RTX 2050 have?", None, "4"),
    Case("history fact", "In which year was the Python programming language first released?", None, "1991"),
    Case("live news", "What is the latest news about the Indian stock market today?", True, may_lack_sources=True),
    Case("general knowledge", "What is the capital of Australia?", False, "canberra"),
]


async def run(voice: bool) -> int:
    import turn_eval

    from Agent_Guru.integration.mcp_tools import install_mcp_policies
    from Agent_Guru.integration.research import ResearchTools, research_server
    from Agent_Guru.memory.memory_manager import MemoryManager

    harness = turn_eval.Harness()
    await harness.start()
    server = research_server()
    server.local = ResearchTools()
    install_mcp_policies(harness.policy, [server])
    right = 0
    for case in CASES:
        harness.memory = MemoryManager(platform_override="eval")
        orch = harness.session()
        orch._mcp_servers = [server]
        orch._start_tools()
        await orch._tools_starting
        started = time.perf_counter()
        if voice:
            result, _ = await harness.say(orch, case.said)
        else:
            result = await orch.run_text_turn(case.said)
        seconds = time.perf_counter() - started
        await orch.close_tools()
        calls = [s.detail.get("tool") for s in result.tool_stages if s.name == "mcp_call"]
        check = next((s.detail for s in result.tool_stages if s.name == "sources_check"), {})
        reply = result.llm_response or ""
        cited = [s["id"] for s in result.sources]
        used_research = bool(calls)
        ok = (case.research is None or used_research == case.research) and (
            case.expect is None or case.expect in reply.lower()
        ) and not check.get("unknown_ids") and not check.get("removed_urls")
        if (case.research or (case.research is None and used_research)) and not case.may_lack_sources:
            ok = ok and bool(cited)
        right += ok
        print(f"{'ok  ' if ok else 'MISS'} {case.name:22} tools={calls} cited={cited} "
              f"removed={check.get('unknown_ids', []) + check.get('removed_urls', [])} "
              f"unmatched={check.get('unmatched', 0)} {seconds:5.1f}s  {reply[:160]!r}")
    await harness.memory.shutdown()
    print(f"\n{right}/{len(CASES)} right")
    return 0 if right == len(CASES) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--voice", action="store_true", help="speak each turn through the streaming path (silent speech)")
    sys.exit(asyncio.run(run(parser.parse_args().voice)))
