"""``GuardedSeat``: bounded retries with the reason fed back (seats.py)."""

from __future__ import annotations

from typing import Any

import pytest
from agent_game_framework.core import Conversable, FreeText, SeatDecision, TextTurn

from wavelength.seats import (
    MAX_ATTEMPTS,
    ClueRejected,
    GuardedSeat,
    GuessRejected,
    guard,
    normalize_clue,
    normalize_guess,
)

OBS = {"spectrum": {"left": "Cold", "right": "Hot"}, "round": 1}
CLUE_REQUEST = [FreeText(max_words=6, max_chars=80)]


class Replies:
    def __init__(self, *actions: Any) -> None:
        self.actions = list(actions)
        self.seen: list[dict[str, Any]] = []

    def decide(self, observation: dict[str, Any], legal_actions: list[Any]) -> SeatDecision[Any]:
        self.seen.append(observation)
        return SeatDecision(action=self.actions.pop(0), banter="hm")


def test_a_fair_clue_passes_straight_through() -> None:
    inner = Replies("a lazy afternoon")
    decision = GuardedSeat(inner).decide(OBS, CLUE_REQUEST)
    assert decision.action == "a lazy afternoon"
    assert decision.banter is None  # a clue turn carries no banter: the psychic knows the target
    assert inner.seen == [OBS]


def test_a_rejected_clue_is_retried_with_the_reason_in_the_observation() -> None:
    inner = Replies("about 70", "a lazy afternoon")
    decision = GuardedSeat(inner).decide(OBS, CLUE_REQUEST)
    assert decision.action == "a lazy afternoon"
    assert inner.seen[1]["previous_clue_rejected"] == "about 70"
    assert "digits" in inner.seen[1]["rejection_reason"]
    assert "rejection_reason" not in OBS  # the caller's observation is untouched


def test_it_gives_up_after_the_attempt_limit() -> None:
    inner = Replies(*["about 70"] * 10)
    with pytest.raises(ClueRejected, match="digits"):
        GuardedSeat(inner).decide(OBS, CLUE_REQUEST)
    assert len(inner.seen) == MAX_ATTEMPTS


GUESS_REQUEST = list(range(101))


def test_a_legal_guess_passes_straight_through() -> None:
    inner = Replies(50)
    assert GuardedSeat(inner).decide(OBS, GUESS_REQUEST).action == 50
    assert inner.seen == [OBS]


@pytest.mark.parametrize(("raw", "guess"), [("35", 35), (" 35\n", 35), (35.0, 35), ("+7", 7)])
def test_a_number_sent_as_text_is_coerced_without_another_call(raw: Any, guess: int) -> None:
    inner = Replies(raw)
    decision = GuardedSeat(inner).decide(OBS, GUESS_REQUEST)
    assert decision.action == guess
    assert type(decision.action) is int
    assert decision.banter == "hm"
    assert len(inner.seen) == 1


def test_an_illegal_guess_is_retried_with_the_range_as_the_reason() -> None:
    inner = Replies("about 40", 101, "40")
    decision = GuardedSeat(inner).decide(OBS, GUESS_REQUEST)
    assert decision.action == 40
    assert inner.seen[1]["previous_guess_rejected"] == "about 40"
    assert inner.seen[2]["previous_guess_rejected"] == 101
    assert inner.seen[1]["rejection_reason"] == "a guess must be a whole number 0-100"
    assert "rejection_reason" not in OBS


@pytest.mark.parametrize("bad", ["about 40", 35.5, True, None, 101, -1, "35 40"])
def test_a_guess_that_is_never_legal_stops_after_the_attempt_limit(bad: Any) -> None:
    inner = Replies(*[bad] * 10)
    with pytest.raises(GuessRejected, match="0-100"):
        GuardedSeat(inner).decide(OBS, GUESS_REQUEST)
    assert len(inner.seen) == MAX_ATTEMPTS


def test_a_non_integer_action_list_is_left_to_the_inner_seat() -> None:
    inner = Replies("up")
    assert GuardedSeat(inner).decide(OBS, ["up", "down"]).action == "up"


@pytest.mark.parametrize(
    ("raw", "clean"), [("35", 35), (" 7 ", 7), (3.0, 3), (3.5, 3.5), ("3.0", "3.0"), (True, True)]
)
def test_normalize_guess_converts_only_unambiguous_integers(raw: Any, clean: Any) -> None:
    assert normalize_guess(raw) == clean
    assert type(normalize_guess(raw)) is type(clean)


def test_chat_capability_is_kept_only_when_the_wrapped_seat_has_it() -> None:
    class Chatty(Replies):
        def respond(self, history: list[Any], incoming: Any) -> TextTurn:
            return TextTurn(text="hi")

    assert isinstance(guard(Chatty()), Conversable)
    assert not isinstance(guard(Replies()), Conversable)


def test_guess_turns_keep_their_banter() -> None:
    assert GuardedSeat(Replies(50)).decide(OBS, list(range(101))).banter == "hm"


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ('"a lazy afternoon"', "a lazy afternoon"),
        ("  'a lazy afternoon'\n", "a lazy afternoon"),
        ("\u201ca lazy afternoon\u201d", "a lazy afternoon"),
        ("\"'nested'\"", "nested"),
        ("it's fine", "it's fine"),
        ('"', '"'),
    ],
)
def test_normalize_clue_removes_wrapping_quotes_only(raw: str, clean: str) -> None:
    assert normalize_clue(raw) == clean


def test_a_wrapped_clue_is_accepted_and_returned_tidy() -> None:
    assert GuardedSeat(Replies('"a lazy afternoon"')).decide(OBS, CLUE_REQUEST).action == (
        "a lazy afternoon"
    )


def test_non_text_passes_through_normalize_for_the_rules_to_reject() -> None:
    assert normalize_clue(7) == 7
