"""Reflective rewriting over a Pareto front: kept candidates are the ones best on some case; adoption goes through the gate."""

from __future__ import annotations

from Agent_Guru.self_improvement.prompt_tuning import evolve, pareto_front


def _scored(passing, median=1.0, failing=()):
    return {"passed": len(passing), "judged": 4, "median_turn_s": median, "passing": sorted(passing),
            "failing": list(failing)}


def test_the_front_keeps_whoever_is_alone_best_on_some_case():
    pool = [
        {"text": "a", "scored": _scored({"q1", "q2"})},
        {"text": "b", "scored": _scored({"q3"})},          # the only one to pass q3: kept
        {"text": "c", "scored": _scored({"q1"})},          # beaten by a on every case: dropped
        {"text": "d", "scored": _scored({"q1", "q2"}, 2.0)},  # same cases as a but slower: dropped
    ]
    assert [c["text"] for c in pareto_front(pool)] == ["a", "b"]  # nosec B101


class World:
    """Guidance text decides which cases pass: each rule names the case it fixes."""

    CASES = ("greet", "time", "maths", "weather")

    def __init__(self, breaks=None):
        self.breaks = breaks
        self.proposed = []

    async def evaluate(self, text):
        passing = {c for c in self.CASES if c == "greet" or f"fix {c}" in text}
        if self.breaks and self.breaks in text:
            passing.discard("greet")
        failing = [f"case {c} failed" for c in self.CASES if c not in passing]
        return _scored(passing, failing=failing)

    async def propose(self, failures, parent):
        self.proposed.append(list(failures))
        case = failures[0].split()[1]
        if self.breaks:
            # Fixes two cases and breaks one that passed: more passes, still not allowed.
            other = failures[1].split()[1]
            return f"- fix {case} - fix {other} {self.breaks}"
        return f"- fix {case}"


async def test_rounds_build_on_failures_and_the_best_is_adopted_through_the_gate():
    world = World()
    result = await evolve(3, propose=world.propose, evaluate=world.evaluate, current="", mistakes=[])
    assert result["adopted"] and result["scored"]["passed"] == 4  # nosec B101
    assert result["guidance"].count("- fix") == 3 and result["tried"] == 3  # nosec B101
    assert world.proposed[0] == ["case time failed", "case maths failed", "case weather failed"]  # nosec B101


async def test_a_rewrite_that_loses_a_passing_case_is_not_adopted():
    world = World(breaks="(and stop greeting)")
    result = await evolve(1, propose=world.propose, evaluate=world.evaluate, current="", mistakes=[])
    assert not result["adopted"] and "now fail" in result["reason"]  # nosec B101


async def test_nothing_to_learn_from_adopts_nothing():
    async def everything_passes(text):
        return _scored({"greet", "time", "maths", "weather"})

    async def never(failures, parent):
        raise AssertionError("asked to rewrite with nothing failing")

    result = await evolve(2, propose=never, evaluate=everything_passes, current="be brief", mistakes=[])
    assert not result["adopted"] and result["tried"] == 0  # nosec B101
