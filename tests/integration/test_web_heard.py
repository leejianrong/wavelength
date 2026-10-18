"""ADR-0013: what a human says aloud. Shown, never a move; only the human guesser's, only in its
own guess turn; given to an AI psychic only after the reveal. No HTTP and no model."""

from __future__ import annotations

import json
import threading
from typing import Any

import pytest
from agent_game_framework.core import SeatDecision
from test_web_session import WAIT, await_turn, next_event
from test_web_thinking import REACTION, FakeBackend, next_event_of

from wavelength.bots import RandomWavelengthBot
from wavelength.seats import guard
from wavelength.web.broadcast import Broadcaster, Subscriber
from wavelength.web.moves import MoveRejected
from wavelength.web.session import MAX_HEARD_CHARS, MAX_SPOKEN_LINES, WebSession

SAID = "this feels like a quiet sunday"


def guesser_session(backend: FakeBackend | None = None) -> tuple[WebSession, Subscriber]:
    """Round 1: the AI is the psychic, the human guesses."""
    fake = backend or FakeBackend()
    broadcaster = Broadcaster()
    session = WebSession(
        ["ai", "you"],
        {"ai": guard(fake)},  # type: ignore[arg-type]
        broadcaster=broadcaster,
        human="you",
        kinds={"ai": "llm", "you": "human"},
        rounds=2,
        seed=5,
    )
    return session, broadcaster.subscribe()


def to_guess_turn(session: WebSession, sub: Subscriber) -> None:
    session.start()
    state = await_turn(sub, "guess")
    assert state["awaiting"] == "guess"


def test_a_human_guessers_words_are_shown_as_a_heard_event_and_never_move_the_needle() -> None:
    session, sub = guesser_session()
    to_guess_turn(session, sub)
    session.heard("this feels", False)
    _, body = next_event_of(sub, "heard")
    assert body == {
        "type": "heard",
        "seat": "you",
        "round": 1,
        "text": "this feels",
        "final": False,
    }
    session.heard(SAID, True)
    _, body = next_event_of(sub, "heard")
    assert body["text"] == SAID and body["final"] is True
    # nothing was a move or a needle: the human is still asked for a guess
    session.submit({"type": "guess", "value": 40})
    assert await_turn(sub)["observation"]["history"][-1]["guess"] == 40
    session.close()


def test_the_wrong_seat_or_shape_or_time_is_refused() -> None:
    session, sub = guesser_session()
    to_guess_turn(session, sub)
    for bad_text in ("", "   ", None, 7, "x" * (MAX_HEARD_CHARS + 1)):
        with pytest.raises(MoveRejected):
            session.heard(bad_text, True)
    with pytest.raises(MoveRejected):
        session.heard(SAID, "yes")
    session.submit({"type": "guess", "value": 40})
    await_turn(sub)  # the human is now the psychic in round 2, awaiting a clue
    with pytest.raises(MoveRejected, match="psychic stays quiet"):
        session.heard(SAID, True)
    session.close()


def test_a_human_psychic_cannot_speak_to_an_ai_guesser_in_the_guess_phase() -> None:
    release = threading.Event()
    arrived = threading.Event()

    class Slow:
        def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
            arrived.set()
            assert release.wait(WAIT)
            return SeatDecision(action=50, banter="ok")

    broadcaster = Broadcaster()
    sub = broadcaster.subscribe()
    session = WebSession(
        ["you", "ai"],
        {"ai": Slow()},
        broadcaster=broadcaster,
        human="you",
        kinds={"you": "human", "ai": "llm"},
        rounds=2,
        seed=5,
    )
    session.start()
    await_turn(sub, "clue")
    with pytest.raises(MoveRejected):
        session.heard("the target is far left", True)  # a clue turn: it stays on the page
    session.submit({"type": "clue", "text": "a lazy afternoon"})
    assert arrived.wait(WAIT)  # the AI is guessing now
    with pytest.raises(MoveRejected, match="psychic stays quiet"):
        session.heard("the target is far left", True)
    seen = []
    while not sub.mailbox.empty():
        seen.append(next_event(sub))
    assert not [1 for e, _ in seen if e == "heard"]
    release.set()
    session.close()


def test_partials_closer_than_the_gap_are_dropped_and_finals_never_are() -> None:
    session, sub = guesser_session()
    to_guess_turn(session, sub)
    session.heard("a", False)
    session.heard("a b", False)  # inside the gap: dropped quietly
    session.heard("a b c", True)  # a finished line is always kept
    heard = []
    while not sub.mailbox.empty():
        event, body = next_event(sub)
        if event == "heard":
            heard.append(body["text"])
    assert heard == ["a", "a b c"]
    session.close()


def test_what_the_human_said_reaches_the_ai_psychic_only_in_its_reaction_after_the_reveal() -> None:
    fake = FakeBackend()
    session, sub = guesser_session(fake)
    to_guess_turn(session, sub)
    session.heard("let me think", False)
    session.heard(SAID, True)
    assert not [p for p in fake.prompts if SAID in p]  # nothing went to the model during the guess
    session.submit({"type": "guess", "value": 40})
    _, reaction = next_event_of(sub, "reaction")
    assert reaction["text"] == REACTION
    with_words = [p for p in fake.prompts if SAID in p]
    assert len(with_words) == 1 and with_words[0].startswith("The round is over")
    assert "let me think" not in with_words[0]  # a partial is never kept
    session.close()


def test_only_the_last_lines_are_kept_and_they_start_again_next_round() -> None:
    fake = FakeBackend()
    session, sub = guesser_session(fake)
    to_guess_turn(session, sub)
    for i in range(MAX_SPOKEN_LINES + 5):
        session.heard(f"line {i}", True)
    session.submit({"type": "guess", "value": 40})
    next_event_of(sub, "reaction")
    prompt = next(p for p in fake.prompts if p.startswith("The round is over"))
    assert "line 24" in prompt and "line 4 " not in prompt and "line 5 " in prompt
    session.close()


def test_a_reloaded_page_is_replayed_the_latest_line() -> None:
    session, sub = guesser_session()
    to_guess_turn(session, sub)
    session.heard(SAID, True)
    late = session._broadcaster.subscribe()
    replayed = {}
    for _ in range(late.mailbox.qsize()):
        event, data = late.get(WAIT)
        replayed[event] = json.loads(data)
    assert replayed["heard"]["text"] == SAID
    session.close()


def test_an_unrelated_bot_psychic_and_a_watch_match_take_no_words() -> None:
    watching = WebSession(
        ["ai-1", "ai-2"],
        {"ai-1": RandomWavelengthBot(), "ai-2": RandomWavelengthBot()},
        broadcaster=Broadcaster(),
    )
    with pytest.raises(MoveRejected):
        watching.heard(SAID, True)
