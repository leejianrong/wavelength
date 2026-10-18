"""V13 (ADR-0011): the needle drafts, the guesser's thoughts and the psychic's reaction, as a
browser would be sent them. No HTTP and no model (fake backends)."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from agent_game_framework.core import SeatDecision, TextTurn, is_free_text
from test_web_session import (
    WAIT,
    await_turn,
    human_session,
    next_event,
    watch_session,
)

from wavelength.eval import CallCapExceeded
from wavelength.seats import guard
from wavelength.thinking import ThinkingSeat
from wavelength.web.broadcast import Subscriber
from wavelength.web.moves import MoveRejected
from wavelength.web.session import WebSession

PSYCHIC_NOTES = "NOTES-PSY the target is {target}, so go for something sunny"
GUESSER_NOTES = "Reading the clue literally. It leans toward the left end. My number is 30."
REACTION = "Ha, so close, I nearly had you!"


class FakeBackend:
    """A model: notes mention the target for a psychic (as real ones do), a guess is 30."""

    def __init__(self, reaction: Any = REACTION) -> None:
        self.reaction = reaction
        self.prompts: list[str] = []

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        if is_free_text(legal_actions) is not None:
            return SeatDecision(action="a sunny afternoon")
        return SeatDecision(action=30, banter="Going with my gut.")

    def respond(self, history: list[Any], incoming: Any) -> TextTurn:
        text = incoming.text
        self.prompts.append(text)
        if text.startswith("The round is over"):
            if isinstance(self.reaction, Exception):
                raise self.reaction
            return TextTurn(text=self.reaction)
        found = re.search(r'"target": (\d+)', text)
        if "You are the psychic" in text and found:
            return TextTurn(text=PSYCHIC_NOTES.format(target=found.group(1)))
        return TextTurn(text=GUESSER_NOTES)


def ai_pair(reaction: Any = REACTION) -> tuple[WebSession, Subscriber, dict[str, FakeBackend]]:
    backends = {"ai-1": FakeBackend(reaction), "ai-2": FakeBackend(reaction)}
    controllers = {p: guard(ThinkingSeat(b)) for p, b in backends.items()}  # type: ignore[arg-type]
    session, sub = watch_session(
        controllers, kinds={"ai-1": "llm", "ai-2": "llm"}, rounds=2, seed=5
    )
    return session, sub, backends


def drain(session: WebSession, sub: Subscriber) -> list[tuple[str, dict[str, Any]]]:
    """Every event of a whole match, in order."""
    session.start()
    events: list[tuple[str, dict[str, Any]]] = []
    while True:
        event, body = next_event(sub)
        events.append((event, body))
        if event == "state" and body["observation"]["phase"] is None:
            break
    session.join(WAIT)
    while not sub.mailbox.empty():
        events.append(next_event(sub))
    session.close()
    return events


def first_reveal(events: list[tuple[str, dict[str, Any]]]) -> int:
    return next(
        i for i, (e, b) in enumerate(events) if e == "state" and b["observation"]["history"]
    )


def test_a_psychics_notes_reach_no_page_before_the_reveal_and_come_with_the_reaction() -> None:
    session, sub, _ = ai_pair()
    events = drain(session, sub)
    reveal = first_reveal(events)
    for _event, body in events[:reveal]:
        assert "NOTES-PSY" not in json.dumps(body)
    reactions = [b for e, b in events[reveal:] if e == "reaction"]
    assert reactions, "an AI psychic reacts after the reveal"
    assert reactions[0]["text"] == REACTION
    assert "NOTES-PSY" in reactions[0]["notes"]
    assert reactions[0]["round"] == 1
    assert set(reactions[0]) == {"type", "seat", "round", "text", "notes"}


def test_the_reaction_comes_from_the_psychic_and_is_one_call_per_round() -> None:
    session, sub, backends = ai_pair()
    events = drain(session, sub)
    states = [b for e, b in events if e == "state"]
    psychics = [r["psychic"] for r in states[-1]["observation"]["history"]]
    reactions = [b for e, b in events if e == "reaction"]
    assert [r["seat"] for r in reactions] == psychics
    for pid, backend in backends.items():
        over = [p for p in backend.prompts if p.startswith("The round is over")]
        assert len(over) == psychics.count(pid)


def test_a_guessers_thoughts_are_public_and_the_needle_locks_on_its_guess() -> None:
    session, sub, _ = ai_pair()
    events = drain(session, sub)
    reveal = first_reveal(events)
    thinking = [b for e, b in events[:reveal] if e == "thinking"]
    assert len(thinking) == 1 and thinking[0]["text"] == GUESSER_NOTES
    assert "NOTES-PSY" not in thinking[0]["text"]
    assert set(thinking[0]) == {"type", "seat", "round", "text"}
    drafts = [b for e, b in events[:reveal] if e == "draft" and b["value"] is not None]
    assert drafts and drafts[-1]["final"] is True and drafts[-1]["value"] == 30
    assert all(not d["final"] for d in drafts[:-1])
    assert all(set(d) == {"type", "seat", "value", "final"} for d in drafts)
    # the guesser draws the needle, and it does so before the reveal reaches the page
    assert {d["seat"] for d in drafts} == {thinking[0]["seat"]}


def test_a_failed_or_capped_reaction_leaves_the_notes_and_no_line() -> None:
    for failure in (RuntimeError("boom with the target 42"), CallCapExceeded("cap")):
        session, sub, _ = ai_pair(reaction=failure)
        events = drain(session, sub)
        reactions = [b for e, b in events if e == "reaction"]
        assert reactions and all(r["text"] is None for r in reactions)
        assert "boom" not in json.dumps(events)


def test_without_thinking_there_is_no_thoughts_event_and_no_notes() -> None:
    backends = {"ai-1": FakeBackend(), "ai-2": FakeBackend()}
    controllers = {p: guard(b) for p, b in backends.items()}  # type: ignore[arg-type]
    session, sub = watch_session(controllers, kinds={"ai-1": "llm", "ai-2": "llm"}, rounds=1)
    events = drain(session, sub)
    assert not [1 for e, _ in events if e == "thinking"]
    assert all(r["notes"] is None for e, r in events if e == "reaction")


def test_a_human_psychic_gets_no_reaction_and_a_human_guesser_no_walk() -> None:
    backend = FakeBackend()
    broadcaster_session, sub = human_session(kinds={"you": "human", "bot": "llm"}, rounds=2)
    # a bot seat is not an AI: no walk, no reaction, no thinking
    broadcaster_session.start()
    seen: list[str] = []
    state = await_turn(sub)
    while state["observation"]["phase"] is not None:
        seen.append("x")
        if state["awaiting"] == "clue":
            broadcaster_session.submit({"type": "clue", "text": "a lazy afternoon"})
        else:
            broadcaster_session.submit({"type": "guess", "value": 50})
        state = await_turn(sub)
    events = []
    while not sub.mailbox.empty():
        events.append(next_event(sub))
    broadcaster_session.close()
    assert backend.prompts == []
    assert not [1 for e, _ in events if e in ("thinking", "reaction")]


def test_a_draft_is_public_only_during_the_humans_guess_and_never_a_move() -> None:
    session, sub = human_session(rounds=2)
    session.start()
    to_guess(session, sub)
    session.draft(61)
    event, body = next_event_of(sub, "draft")
    assert body == {"type": "draft", "seat": "you", "value": 61, "final": False}
    # a draft is not a move: the human is still being asked
    session.submit({"type": "guess", "value": 40})
    state = await_turn(sub)
    assert state["observation"]["history"][-1]["guess"] == 40
    session.close()


def to_guess(session: WebSession, sub: Subscriber) -> None:
    """Play clues (and let the bot guess) until the human is asked for a guess."""
    state = await_turn(sub)
    while state["awaiting"] != "guess":
        assert state["observation"]["phase"] is not None
        session.submit({"type": "clue", "text": "a lazy afternoon"})
        state = await_turn(sub)


def next_event_of(sub: Subscriber, name: str) -> tuple[str, dict[str, Any]]:
    while True:
        event, body = next_event(sub)
        if event == name:
            return event, body


def test_a_draft_is_refused_out_of_turn_out_of_range_or_with_no_human() -> None:
    session, sub = human_session(rounds=2)
    session.start()
    state = await_turn(sub)
    assert state["awaiting"] == "clue"
    with pytest.raises(MoveRejected):
        session.draft(50)  # a clue turn
    session.submit({"type": "clue", "text": "a lazy afternoon"})
    to_guess(session, sub)
    for bad in (101, -1, 5.5, "50", True, None):
        with pytest.raises(MoveRejected):
            session.draft(bad)
    session.close()
    watching, _ = watch_session()
    with pytest.raises(MoveRejected):
        watching.draft(50)


def test_drafts_closer_than_the_gap_are_dropped_quietly(monkeypatch: pytest.MonkeyPatch) -> None:
    session, sub = human_session(rounds=2)
    session.start()
    to_guess(session, sub)
    session.draft(10)
    session.draft(11)  # inside the gap: dropped, not an error
    session.draft(12)
    drafts: list[dict[str, Any]] = []
    while not sub.mailbox.empty():
        event, body = next_event(sub)
        if event == "draft" and body["value"] is not None:
            drafts.append(body)
    assert [d["value"] for d in drafts] == [10]
    session.close()


def test_a_reloaded_page_is_sent_the_needle_and_thoughts_on_show() -> None:
    session, sub, _ = ai_pair()
    session.start()
    while True:
        event, body = next_event(sub)
        if event == "thinking":
            break
    late = session._broadcaster.subscribe()
    replayed = {next_event(late)[0] for _ in range(late.mailbox.qsize())}
    assert "thinking" in replayed
    session.close()
