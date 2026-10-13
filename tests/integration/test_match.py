"""The engine driven through the framework's ``Match``, with scripted seats."""

from __future__ import annotations

import json
import random
from typing import Any

import pytest
from agent_game_framework.core import IllegalActionError, Match, SeatDecision

from wavelength.bots import RandomWavelengthBot
from wavelength.engine import WavelengthEngine


class Scripted:
    """A seat that plays a fixed list of actions, whatever it is asked."""

    def __init__(self, *actions: Any) -> None:
        self._actions = list(actions)

    def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
        return SeatDecision(action=self._actions.pop(0))


def match(seats: dict[str, Any] | None = None, **config: Any) -> Match[Any, Any, Any]:
    config.setdefault("seed", 11)
    return Match(WavelengthEngine(), players=["A", "B"], config=config, seats=seats)


def test_all_bot_match_runs_to_the_end_with_alternating_psychics() -> None:
    seats = {
        "A": RandomWavelengthBot(random.Random(1)),
        "B": RandomWavelengthBot(random.Random(2)),
    }
    m = match(seats, rounds=6)
    seen: list[str] = []
    m.run_to_completion(on_turn=lambda p, d: seen.append(p))

    assert m.is_terminal()
    assert seen == ["A", "B", "B", "A"] * 3  # clue, guess, then roles swap
    assert len(m.observation_for("A")["history"]) == 6
    assert m.winners() in ([], ["A", "B"])


def test_illegal_action_leaves_serialized_state_byte_identical() -> None:
    m = match()
    m.submit_action("A", "a lazy afternoon")
    before = json.dumps(m.serialize(), sort_keys=True)

    for player, action in (("B", 101), ("A", "too late"), ("B", "not a number")):
        with pytest.raises(IllegalActionError):
            m.submit_action(player, action)
    assert json.dumps(m.serialize(), sort_keys=True) == before


def test_rejected_clue_is_asked_again_via_the_framework_hook() -> None:
    seats = {"A": Scripted("about 70", "a lazy afternoon"), "B": Scripted(50)}
    m = match(seats, rounds=1)
    rejected: list[str] = []

    m.run_to_completion(on_illegal_action=lambda p, d, e: rejected.append(str(e)))

    assert rejected and "digits" in rejected[0]
    assert m.is_terminal()


def test_serialize_restore_finishes_identically_to_an_uninterrupted_run() -> None:
    def seats() -> dict[str, Any]:
        return {
            "A": RandomWavelengthBot(random.Random(5)),
            "B": RandomWavelengthBot(random.Random(6)),
        }

    full = match(seats(), rounds=4)
    full.run_to_completion()

    part = match(seats(), rounds=4)
    for _ in range(5):
        part.play_turn()
    resumed = match(seats(), rounds=4)
    resumed.deserialize(json.loads(json.dumps(part.serialize())))
    # a fresh pair of bots replays from a different rng position, so compare
    # structure, not guesses: same plan, same state at the cut
    assert resumed.serialize() == part.serialize()
    resumed.run_to_completion()
    assert resumed.is_terminal()
    assert [r["target"] for r in resumed.observation_for("A")["history"]] == [
        r["target"] for r in full.observation_for("A")["history"]
    ]


def test_no_observation_leaks_before_the_reveal_in_any_phase_for_any_viewer() -> None:
    """The leak scan (R2): at every step of a whole match, the guesser's view
    holds neither the current target nor any plan of rounds to come."""
    m = match(rounds=3, seed=21)
    state = m.state
    plan = state.plan
    while not m.is_terminal():
        current = m.current_players()[0]
        index = m.state.round_index
        for viewer in ("A", "B"):
            obs = m.observation_for(viewer)
            blob = json.dumps(obs)
            if obs["role"] == "guesser":
                assert "target" not in obs
                assert f'"target": {plan[index].target}' not in blob
            for later in plan[index + 1 :]:
                assert later.spectrum.to_dict() != obs.get("spectrum")
                assert json.dumps(later.spectrum.to_dict()) not in blob
        action = (
            "a lazy afternoon"
            if m.state.phase == "clue"
            else RandomWavelengthBot().decide({}, m.legal_actions(current)).action
        )
        m.submit_action(current, action)


def test_a_match_resumed_from_a_midway_dump_replays_the_rest_identically() -> None:
    """Bots are deterministic given the observation, so a restored match must
    finish exactly as the uninterrupted one did, not just structurally alike."""

    def fresh() -> Match[Any, Any, Any]:
        seats = {"A": RandomWavelengthBot(), "B": RandomWavelengthBot()}
        return match(seats, rounds=6, seed=17)

    whole: list[tuple[str, Any]] = []
    full = fresh()
    full.run_to_completion(on_turn=lambda p, d: whole.append((p, d.action)))

    first_half: list[tuple[str, Any]] = []
    part = fresh()
    for _ in range(7):  # mid-round: a clue is in, its guess is not
        part.play_turn(on_turn=lambda p, d: first_half.append((p, d.action)))
    dump = json.loads(json.dumps(part.serialize()))

    second_half: list[tuple[str, Any]] = []
    resumed = fresh()
    resumed.deserialize(dump)
    resumed.run_to_completion(on_turn=lambda p, d: second_half.append((p, d.action)))

    assert first_half + second_half == whole
    assert resumed.serialize() == full.serialize()
