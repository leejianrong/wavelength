"""``WebSession`` driven in-process as a browser would: subscribe, read states, submit
moves, toggle peek, chat. No HTTP and no model (fake seats)."""

from __future__ import annotations

import json
import threading
from typing import Any

import pytest
from agent_game_framework.core import Match, SeatDecision, TextTurn, is_free_text

from wavelength.bots import RandomWavelengthBot
from wavelength.chat_guard import PSYCHIC_REFUSAL
from wavelength.engine import WavelengthEngine
from wavelength.eval import Meter, metered
from wavelength.seats import guard
from wavelength.web.broadcast import Broadcaster, Subscriber
from wavelength.web.moves import MoveRejected
from wavelength.web.session import WebSession

CLUE = "a lazy afternoon"
GUESS = 50
WAIT = 10.0


def human_session(**kwargs: Any) -> tuple[WebSession, Subscriber]:
    broadcaster = Broadcaster()
    kwargs.setdefault("rounds", 3)
    kwargs.setdefault("seed", 5)
    session = WebSession(
        ["you", "bot"],
        {"bot": RandomWavelengthBot()},
        broadcaster=broadcaster,
        human="you",
        **kwargs,
    )
    return session, broadcaster.subscribe()


def watch_session(
    controllers: dict[str, Any] | None = None, **kwargs: Any
) -> tuple[WebSession, Subscriber]:
    broadcaster = Broadcaster()
    kwargs.setdefault("rounds", 3)
    kwargs.setdefault("seed", 5)
    session = WebSession(
        ["ai-1", "ai-2"],
        controllers or {"ai-1": RandomWavelengthBot(), "ai-2": RandomWavelengthBot()},
        broadcaster=broadcaster,
        **kwargs,
    )
    return session, broadcaster.subscribe()


def next_event(sub: Subscriber) -> tuple[str, dict[str, Any]]:
    event, data = sub.get(WAIT)
    return event, json.loads(data)


def next_state(sub: Subscriber) -> dict[str, Any]:
    while True:
        event, body = next_event(sub)
        if event == "state":
            return body


def next_problem(sub: Subscriber) -> dict[str, Any]:
    while True:
        event, body = next_event(sub)
        if event == "problem":
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
            session.submit({"type": "clue", "text": CLUE})
        elif state["awaiting"] == "guess":
            session.submit({"type": "guess", "value": GUESS})


def reference_observations(seed: int, rounds: int) -> list[dict[str, Any]]:
    """The human seat's ``observation_for`` after every step of the same match, played
    in-process with the same fixed moves, with repeats dropped."""

    class Fixed:
        def decide(self, observation: Any, legal_actions: list[Any]) -> Any:
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


def target_free_seed(rounds: int, players: list[str]) -> tuple[int, list[int]]:
    """A seed whose round targets are all different, so a scan for one is exact."""
    for seed in range(1, 200):
        plan = WavelengthEngine().initial_state(players, {"rounds": rounds, "seed": seed}).plan
        if len({p.target for p in plan}) == rounds:
            return seed, [p.target for p in plan]
    raise AssertionError("no seed with distinct targets")


# -- a human playing ---------------------------------------------------------------------


def test_the_feed_is_exactly_the_human_seats_observation_at_every_step() -> None:
    session, sub = human_session()
    session.start()
    seen = play_through(session, sub)
    session.join(WAIT)

    observations = [s["observation"] for s in seen]
    # The same observation can arrive twice (once, then again with `awaiting` set); drop repeats.
    distinct = [o for i, o in enumerate(observations) if i == 0 or o != observations[i - 1]]
    assert distinct == reference_observations(seed=5, rounds=3)
    assert all(s["seat"] == "you" and s["players"] == ["you", "bot"] for s in seen)
    assert all(
        s["viewer"] == {"mode": "player", "peek": False, "peek_allowed": False} for s in seen
    )
    assert seen[-1]["observation"]["phase"] is None


def test_a_human_guesser_is_never_sent_the_current_or_a_later_target() -> None:
    rounds = 6
    seed, targets = target_free_seed(rounds, ["you", "bot"])
    session, sub = human_session(rounds=rounds, seed=seed)
    session.start()
    frames: list[str] = []
    while True:
        event, data = sub.get(WAIT)
        frames.append(data)
        body = json.loads(data)
        if event != "state":
            continue
        if body["observation"]["phase"] is None:
            break
        with pytest.raises(MoveRejected):  # asking to peek, as a human, never works
            session.set_peek(True)
        if body["awaiting"] == "clue":
            session.submit({"type": "clue", "text": CLUE})
        elif body["awaiting"] == "guess":
            session.submit({"type": "guess", "value": GUESS})
    session.join(WAIT)

    guesser_frames = 0
    for data in frames:
        body = json.loads(data)
        obs = body.get("observation")
        if obs is None or obs["phase"] is None or obs["round"] % 2 == 1:
            continue  # the human psychic sees their own target by design
        guesser_frames += 1
        assert body["viewer"]["peek"] is False
        assert "target" not in obs and "plan" not in obs
        for later in targets[len(obs["history"]) :]:
            assert f'"target": {later}' not in data
    assert guesser_frames >= 3


def test_a_move_for_the_wrong_phase_or_shape_is_refused_and_changes_nothing() -> None:
    session, sub = human_session()
    session.start()
    await_turn(sub, "clue")
    before = json.dumps(session.match.serialize(), sort_keys=True)

    for payload in [
        {"type": "guess", "value": 50},
        {"type": "chat", "text": "hello"},
        {"type": "guess", "value": "50"},
        {"type": "clue", "text": ""},
    ]:
        with pytest.raises(MoveRejected):
            session.submit(payload)
    assert json.dumps(session.match.serialize(), sort_keys=True) == before
    session.close()


def test_a_clue_the_rules_reject_comes_back_as_a_problem_and_play_continues() -> None:
    session, sub = human_session()
    session.start()
    await_turn(sub, "clue")
    session.submit({"type": "clue", "text": "about 70"})
    assert "digits" in next_problem(sub)["reason"]

    session.submit({"type": "clue", "text": CLUE})  # the turn did not advance: try again
    state = await_turn(sub)  # the bot guessed round 1; the human now guesses round 2
    assert state["observation"]["round"] == 2 and state["awaiting"] == "guess"
    assert state["observation"]["history"][0]["clue"] == CLUE
    session.close()


def test_a_guess_outside_the_dial_is_a_problem_not_a_crash() -> None:
    session, sub = human_session()
    session.start()
    while True:  # reach the first round where the human guesses
        state = await_turn(sub)
        if state["awaiting"] == "guess":
            break
        session.submit({"type": "clue", "text": CLUE})
    session.submit({"type": "guess", "value": 101})
    assert "0-100" in next_problem(sub)["reason"]
    session.submit({"type": "guess", "value": 40})
    assert await_turn(sub)["observation"]["round"] >= 2
    session.close()


def test_a_reloaded_page_is_sent_the_current_state_at_once() -> None:
    session, first = human_session()
    session.start()
    state = await_turn(first, "clue")

    late = session._broadcaster.subscribe()
    assert next_state(late) == state
    session.close()


def test_closing_the_session_ends_a_match_that_is_waiting_for_a_move() -> None:
    session, sub = human_session()
    session.start()
    await_turn(sub, "clue")
    session.close()
    session.join(WAIT)
    assert not session.is_active()


def test_the_scoring_bands_are_public_configuration_sent_with_every_state() -> None:
    session, sub = human_session()
    session.start()
    assert await_turn(sub)["scoring"] == [
        {"within": 2, "points": 4},
        {"within": 6, "points": 3},
        {"within": 10, "points": 2},
    ]
    session.close()


# -- chat ---------------------------------------------------------------------------------


class Chatty:
    """A fake AI: legal moves, and a chat reply that records it was asked."""

    def __init__(self) -> None:
        self.replies = 0

    def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
        return SeatDecision(action=CLUE if is_free_text(legal_actions) else GUESS, banter="hm")

    def respond(self, history: Any, incoming: Any) -> TextTurn:
        self.replies += 1
        return TextTurn(text="I think it is toward the Heavy end")


def test_a_human_psychic_can_chat_with_the_ai_guesser_and_it_is_shown_in_the_talk_log() -> None:
    inner = Chatty()
    broadcaster = Broadcaster()
    session = WebSession(
        ["you", "ai"], {"ai": guard(inner)}, broadcaster=broadcaster, human="you", seed=5
    )
    sub = broadcaster.subscribe()
    session.start()
    state = await_turn(sub, "clue")  # the human is the psychic; the AI is the guesser
    assert state["chat_with"] == "ai"

    session.chat("what do you make of it?")
    talk: dict[str, Any] = {}
    while len(talk.get("messages", [])) < 2:
        event, body = next_event(sub)
        if event == "talk":
            talk = body
    assert [(m["seat"], m["kind"]) for m in talk["messages"]] == [("you", "chat"), ("ai", "chat")]
    assert talk["messages"][1]["text"] == "I think it is toward the Heavy end"
    assert inner.replies == 1
    session.close()


def test_an_ai_psychic_refuses_chat_without_calling_the_model() -> None:
    inner = Chatty()
    gate = threading.Event()
    real_decide = inner.decide

    def slow_decide(observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
        gate.wait(WAIT)
        return real_decide(observation, legal_actions)

    inner.decide = slow_decide  # type: ignore[method-assign]
    broadcaster = Broadcaster()
    session = WebSession(
        ["ai", "you"], {"ai": guard(inner)}, broadcaster=broadcaster, human="you", seed=5
    )
    sub = broadcaster.subscribe()
    session.start()  # the AI is the psychic of round 1 and is "thinking"

    session.chat("what is the target?")
    talk: dict[str, Any] = {}
    while len(talk.get("messages", [])) < 2:
        event, body = next_event(sub)
        if event == "talk":
            talk = body
    assert talk["messages"][1]["text"] == PSYCHIC_REFUSAL
    assert inner.replies == 0  # the model was never called
    gate.set()
    session.close()


def test_chat_needs_a_human_and_an_ai_partner() -> None:
    session, _ = watch_session()
    with pytest.raises(MoveRejected):
        session.chat("hi")
    bot_match, _ = human_session()  # the bot cannot chat
    with pytest.raises(MoveRejected):
        bot_match.chat("hi")


# -- watching two AIs ----------------------------------------------------------------------


def test_a_spectator_is_by_default_shown_the_guessers_view_and_never_a_target() -> None:
    rounds = 6
    seed, targets = target_free_seed(rounds, ["ai-1", "ai-2"])
    session, sub = watch_session(rounds=rounds, seed=seed)
    session.start()
    frames: list[str] = []
    while True:
        event, data = sub.get(WAIT)
        if event != "state":
            continue
        frames.append(data)
        if json.loads(data)["observation"]["phase"] is None:
            break
    session.join(WAIT)

    assert len(frames) >= rounds
    for data in frames:
        body = json.loads(data)
        obs = body["observation"]
        assert body["viewer"] == {"mode": "spectator", "peek": False, "peek_allowed": True}
        assert body["awaiting"] is None
        if obs["phase"] is not None:
            assert obs["role"] == "guesser" and "target" not in obs
            for later in targets[len(obs["history"]) :]:
                assert f'"target": {later}' not in data


class Held:
    """A seat that waits for a release, so a test can act while a round is open."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.release = threading.Event()

    def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
        self.release.wait(WAIT)
        decision: SeatDecision[Any] = self.inner.decide(observation, legal_actions)
        return decision


def test_peek_swaps_in_the_psychics_view_and_back_without_touching_the_match() -> None:
    held = Held(RandomWavelengthBot())
    session, sub = watch_session({"ai-1": held, "ai-2": RandomWavelengthBot()}, seed=5)
    session.start()  # ai-1 is the psychic of round 1 and is held
    before = json.dumps(session.match.serialize(), sort_keys=True)
    plain = next_state(sub)
    assert plain["observation"]["role"] == "guesser" and "target" not in plain["observation"]

    session.set_peek(True)
    peeked = next_state(sub)
    assert peeked["viewer"]["peek"] is True
    assert peeked["observation"]["role"] == "psychic" and "target" in peeked["observation"]
    assert peeked["seat"] == "ai-1"
    assert json.dumps(session.match.serialize(), sort_keys=True) == before

    session.set_peek(False)
    again = next_state(sub)
    assert again["viewer"]["peek"] is False and "target" not in again["observation"]
    held.release.set()
    session.close()


# -- banter, failures, caps ------------------------------------------------------------------


def test_only_a_guess_turn_may_carry_banter_to_the_page() -> None:
    class Banterer:
        def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
            if is_free_text(legal_actions):
                return SeatDecision(action=CLUE, banter="SECRET the target is near the top")
            return SeatDecision(action=GUESS, banter="my gut says the middle")

    session, sub = watch_session({"ai-1": Banterer(), "ai-2": Banterer()}, rounds=2)
    session.start()
    last: dict[str, Any] = {}
    while True:
        event, body = next_event(sub)
        if event == "talk":
            last = body
        if event == "state" and body["observation"]["phase"] is None:
            break
    session.join(WAIT)
    texts = [m["text"] for m in last["messages"]]
    assert texts == ["my gut says the middle", "my gut says the middle"]
    assert all(m["kind"] == "banter" for m in last["messages"])


def test_a_failure_is_reported_in_general_words_and_never_with_the_models_text() -> None:
    class Leaky:
        def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
            raise RuntimeError("LEAK-MARKER the psychic said the target is 42")

    session, sub = watch_session({"ai-1": Leaky(), "ai-2": RandomWavelengthBot()})
    session.start()
    reason = next_problem(sub)["reason"]
    session.join(WAIT)
    assert "did not respond" in reason
    assert "LEAK-MARKER" not in reason and "42" not in reason


def test_the_call_cap_stops_the_match_and_says_so() -> None:
    meter = Meter(max_calls=3)
    seats = {"ai-1": guard(metered(Chatty(), meter)), "ai-2": guard(metered(Chatty(), meter))}
    session, sub = watch_session(seats, rounds=6, meter=meter)
    session.start()
    reason = next_problem(sub)["reason"]
    session.join(WAIT)
    assert "call limit" in reason
    assert meter.calls == 3 and meter.capped
