"""``WebSession`` driven in-process as a browser would: subscribe, read states,
submit moves. No HTTP, no model."""

from __future__ import annotations

import json
import queue
from typing import Any

import pytest
from agent_game_framework.core import Match

from wavelength.bots import RandomWavelengthBot
from wavelength.engine import WavelengthEngine
from wavelength.web.moves import MoveRejected
from wavelength.web.session import Subscriber, WebSession

CLUE = "a lazy afternoon"
GUESS = 50
WAIT = 10.0


def new_session(**kwargs: Any) -> WebSession:
    kwargs.setdefault("rounds", 3)
    kwargs.setdefault("seed", 5)
    return WebSession(RandomWavelengthBot(), **kwargs)


def next_event(sub: Subscriber) -> tuple[str, dict[str, Any]]:
    event, data = sub.get(WAIT)
    return event, json.loads(data)


def next_state(sub: Subscriber) -> dict[str, Any]:
    while True:
        event, body = next_event(sub)
        if event == "state":
            return body


def await_turn(sub: Subscriber, awaiting: str | None = None) -> dict[str, Any]:
    """The next state in which the human is to move (or, with ``awaiting``, that move)."""
    while True:
        state = next_state(sub)
        if state["awaiting"] and (awaiting is None or state["awaiting"] == awaiting):
            return state
        if state["observation"]["phase"] is None:
            return state


def play_through(session: WebSession, sub: Subscriber) -> list[dict[str, Any]]:
    """Play every human turn (a fixed clue, a fixed guess); return every state seen."""
    seen: list[dict[str, Any]] = []
    while True:
        state = next_state(sub)
        seen.append(state)
        if state["observation"]["phase"] is None:
            return seen
        if state["awaiting"] == "clue":
            session.submit("you", {"type": "clue", "text": CLUE})
        elif state["awaiting"] == "guess":
            session.submit("you", {"type": "guess", "value": GUESS})


def reference_observations(seed: int, rounds: int) -> list[dict[str, Any]]:
    """The human seat's ``observation_for`` after every step of the same match,
    played in-process with the same fixed moves, with repeats dropped."""

    class Fixed:
        def decide(self, observation: Any, legal_actions: list[Any]) -> Any:
            from agent_game_framework.core import SeatDecision, is_free_text

            return SeatDecision(action=CLUE if is_free_text(legal_actions) else GUESS)

    m: Match[Any, Any, Any] = Match(
        WavelengthEngine(),
        players=["you", "bot"],
        config={"rounds": rounds, "seed": seed},
        seats={"you": Fixed(), "bot": RandomWavelengthBot()},
    )
    seen = [m.observation_for("you")]
    m.run_to_completion(on_turn=lambda p, d: seen.append(m.observation_for("you")))
    return [o for i, o in enumerate(seen) if i == 0 or o != seen[i - 1]]


def test_the_feed_is_exactly_the_human_seats_observation_at_every_step() -> None:
    session = new_session()
    sub = session.subscribe("you")
    session.start()
    seen = play_through(session, sub)
    session.join(WAIT)

    assert [s["observation"] for s in seen] == reference_observations(seed=5, rounds=3)
    assert all(s["seat"] == "you" and s["players"] == ["you", "bot"] for s in seen)
    assert seen[-1]["observation"]["phase"] is None
    assert seen[-1]["observation"]["total_score"] == sum(
        r["points"] for r in seen[-1]["observation"]["history"]
    )


def target_free_seed(rounds: int) -> int:
    """A seed whose round targets are all different, so a scan for one is exact."""
    for seed in range(1, 200):
        plan = WavelengthEngine().initial_state(["you", "bot"], {"rounds": rounds, "seed": seed})
        if len({p.target for p in plan.plan}) == rounds:
            return seed
    raise AssertionError("no seed with distinct targets")


def test_a_guesser_is_never_sent_the_current_or_a_later_target() -> None:
    rounds = 6
    seed = target_free_seed(rounds)
    targets = [
        p.target
        for p in WavelengthEngine()
        .initial_state(["you", "bot"], {"rounds": rounds, "seed": seed})
        .plan
    ]
    session = new_session(rounds=rounds, seed=seed)
    sub = session.subscribe("you")
    session.start()
    frames: list[tuple[str, str]] = []
    while True:
        event, data = sub.get(WAIT)
        frames.append((event, data))
        body = json.loads(data)
        if event == "state":
            obs = body["observation"]
            if obs["phase"] is None:
                break
            if body["awaiting"] == "clue":
                session.submit("you", {"type": "clue", "text": CLUE})
            elif body["awaiting"] == "guess":
                session.submit("you", {"type": "guess", "value": GUESS})
    session.join(WAIT)

    guesser_frames = 0
    for event, data in frames:
        body = json.loads(data)
        obs = body["observation"]
        # who the human is comes from the schedule (the psychic alternates, the human
        # starts as psychic), never from the observation under test
        if event != "state" or obs["phase"] is None or obs["round"] % 2 == 1:
            continue
        guesser_frames += 1
        assert obs["role"] == "guesser"
        assert "target" not in obs and "plan" not in obs
        for later in targets[len(obs["history"]) :]:
            assert f'"target": {later}' not in data
    assert guesser_frames >= 3  # the human was the guesser in half the rounds


def test_a_move_for_the_wrong_phase_or_seat_is_refused_and_changes_nothing() -> None:
    session = new_session()
    sub = session.subscribe("you")
    session.start()
    state = await_turn(sub, "clue")
    before = json.dumps(session.match.serialize(), sort_keys=True)

    for seat, payload in [
        ("you", {"type": "guess", "value": 50}),
        ("bot", {"type": "clue", "text": CLUE}),
        ("you", {"type": "chat", "text": "hello"}),
        ("you", {"type": "guess", "value": "50"}),
    ]:
        with pytest.raises(MoveRejected):
            session.submit(seat, payload)
    assert json.dumps(session.match.serialize(), sort_keys=True) == before
    assert state["awaiting"] == "clue"
    session.close()


def test_a_clue_the_rules_reject_comes_back_as_an_error_and_play_continues() -> None:
    session = new_session()
    sub = session.subscribe("you")
    session.start()
    await_turn(sub, "clue")
    session.submit("you", {"type": "clue", "text": "about 70"})

    event, body = next_event(sub)
    while event != "problem":
        event, body = next_event(sub)
    assert body["type"] == "problem" and "digits" in body["reason"]

    session.submit("you", {"type": "clue", "text": CLUE})  # the turn did not advance: try again
    state = await_turn(sub)  # the bot guessed round 1; the human now guesses round 2
    assert state["observation"]["round"] == 2 and state["awaiting"] == "guess"
    assert state["observation"]["history"][0]["clue"] == CLUE
    session.close()


def test_a_guess_outside_the_dial_is_an_error_not_a_crash() -> None:
    session = new_session()
    sub = session.subscribe("you")
    session.start()
    while True:  # reach the first round where the human guesses
        state = await_turn(sub)
        if state["awaiting"] == "guess":
            break
        session.submit("you", {"type": "clue", "text": CLUE})
    session.submit("you", {"type": "guess", "value": 101})
    event, body = next_event(sub)
    while event != "problem":
        event, body = next_event(sub)
    assert "0-100" in body["reason"]
    session.submit("you", {"type": "guess", "value": 40})
    assert await_turn(sub)["observation"]["round"] >= 2
    session.close()


def test_a_reloaded_page_is_sent_the_current_state_at_once() -> None:
    session = new_session()
    first = session.subscribe("you")
    session.start()
    state = await_turn(first, "clue")

    late = session.subscribe("you")
    assert next_state(late) == state
    session.close()


def test_only_the_human_seat_can_be_watched() -> None:
    session = new_session()
    with pytest.raises(KeyError):
        session.subscribe("bot")


def test_closing_the_session_ends_a_match_that_is_waiting_for_a_move() -> None:
    session = new_session()
    sub = session.subscribe("you")
    session.start()
    await_turn(sub, "clue")
    session.close()
    session.join(WAIT)
    assert not session._thread.is_alive()


def test_two_sessions_with_one_seed_show_the_same_first_spectrum() -> None:
    a, b = new_session(seed=9), new_session(seed=9)
    sa, sb = a.subscribe("you"), b.subscribe("you")
    a.start()
    b.start()
    assert await_turn(sa)["observation"]["spectrum"] == await_turn(sb)["observation"]["spectrum"]
    a.close()
    b.close()


def test_the_scoring_bands_are_public_configuration_sent_with_every_state() -> None:
    session = new_session()
    sub = session.subscribe("you")
    session.start()
    state = await_turn(sub)
    assert state["scoring"] == [
        {"within": 2, "points": 4},
        {"within": 6, "points": 3},
        {"within": 10, "points": 2},
    ]
    session.close()


def test_nothing_is_queued_for_an_unsubscribed_page() -> None:
    session = new_session()
    sub = session.subscribe("you")
    session.unsubscribe(sub)
    session.start()
    with pytest.raises(queue.Empty):
        sub.get(0.3)
    session.close()
