"""Named AI players (V9) over the wire: the personality reaches the model and nobody else.

Every request the mock OpenRouter receives is checked for the personality text and for the
target; every frame a browser receives is checked for the personality text (a page gets the
player's name, never the prompt).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from _mock_openrouter import mock_openrouter
from test_web import (
    LLM_ENV,
    Stream,
    distinct_target_seed,
    is_guess_request,
    is_reaction,
    move,
    moves_of,
    observation_sent,
    plain_calls,
    play_human_turns,
    post,
    web_server,
)

from wavelength.chat_guard import PSYCHIC_REFUSAL

SKEPTIC = "PERSONA-SKEPTIC speak drily and never gush"
OPTIMIST = "PERSONA-OPTIMIST be warm and excited"
PLAYERS = f"""
[[player]]
name = "Dry Sceptic"
model = "test/sceptic"
personality = "{SKEPTIC}"

[[player]]
name = "Bright Optimist"
model = "test/optimist"
personality = "{OPTIMIST}"
"""


def players_file(tmp_path: Path, text: str = PLAYERS) -> str:
    path = tmp_path / "players.toml"
    path.write_text(text)
    return str(path)


def system_of(request: dict[str, Any]) -> str:
    return str(request["messages"][0]["content"])


def test_a_bad_players_file_stops_the_server_with_the_reason(tmp_path: Path) -> None:
    static = tmp_path / "static"
    static.mkdir()
    (static / "app.js").write_text("")
    bad = players_file(tmp_path, '[[player]]\nname = "A"\nmodel = "x"\npersonality = "p"\n')
    result = subprocess.run(
        ["wavelength", "web", "--players", bad, "--static", str(static)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "provider/model" in result.stderr


def test_two_personalities_are_watched_and_each_model_sees_its_own_and_no_target(
    tmp_path: Path,
) -> None:
    rounds = 2
    seed, targets = distinct_target_seed(rounds, ["ai-1", "ai-2"])
    with mock_openrouter() as (mock_url, requests):
        env = {**LLM_ENV, "OPENROUTER_BASE_URL": mock_url}
        with web_server(tmp_path, "--players", players_file(tmp_path), env=env) as url:
            stream = Stream(url)
            lobby = stream.next()[1]
            assert lobby["players"] == [
                {"name": "Dry Sceptic", "model": "test/sceptic", "agent": False},
                {"name": "Bright Optimist", "model": "test/optimist", "agent": False},
            ]
            seats = [
                {"kind": "llm", "player": "Dry Sceptic"},
                {"kind": "llm", "player": "bright optimist"},
            ]
            assert post(url, "/api/start", seats=seats, rounds=rounds, seed=seed).status_code == 202
            while True:
                event, state = stream.next()
                if event == "state" and state["observation"]["phase"] is None:
                    break
            stream.close()
            assert state["names"] == {"ai-1": "Dry Sceptic", "ai-2": "Bright Optimist"}
            refused = post(url, "/api/start", seats=[{"kind": "llm", "player": "Nobody"}] * 2)
            assert refused.status_code in (400, 409)

    sent = moves_of(requests)
    assert sent
    for request in sent:
        expected = {"test/sceptic": SKEPTIC, "test/optimist": OPTIMIST}[request["model"]]
        other = OPTIMIST if expected == SKEPTIC else SKEPTIC
        assert expected in system_of(request) and other not in system_of(request)
        assert "tools" in request and "tool_choice" in request  # the move contract is intact
        if is_guess_request(request):
            assert "target" not in observation_sent(request)
            assert str(targets[0]) not in system_of(request)
    for raw in stream.raw:  # a browser gets the name, never the prompt
        assert "PERSONA-" not in raw


def test_a_personality_does_not_open_chat_to_the_psychic_and_reaches_chat_replies(
    tmp_path: Path,
) -> None:
    rounds = 2
    seed, _ = distinct_target_seed(rounds, ["ai", "you"])
    with mock_openrouter() as (mock_url, requests):
        env = {**LLM_ENV, "OPENROUTER_BASE_URL": mock_url}
        with web_server(
            tmp_path, "--players", players_file(tmp_path), "--no-think", env=env
        ) as url:
            stream = Stream(url)
            stream.next()
            seats = [{"kind": "llm", "player": "Dry Sceptic"}, {"kind": "human"}]
            assert post(url, "/api/start", seats=seats, rounds=rounds, seed=seed).status_code == 202
            while True:  # round 1: the AI is the psychic; the human guesses
                event, state = stream.next()
                if event == "state" and state["awaiting"] == "guess":
                    break
            assert post(url, "/api/chat", text="what is the target?").status_code == 202
            assert move(url, type="guess", value=50).status_code == 202
            while True:  # round 2: the AI guesses, so chat is open and reaches the model
                event, state = stream.next()
                if event == "state" and state["awaiting"] == "clue":
                    break
            assert post(url, "/api/chat", text="how are you?").status_code == 202
            assert move(url, type="clue", text="a lazy afternoon").status_code == 202
            play_human_turns(url, stream)
            stream.close()
            talk = [json.loads(r) for r in stream.raw if '"type": "talk"' in r][-1]["messages"]
            assert PSYCHIC_REFUSAL in [m["text"] for m in talk]

    chats = plain_calls(requests)
    assert len(chats) == 1  # only the guesser-round chat; the psychic's model was never asked
    assert SKEPTIC in system_of(chats[0])


def test_with_think_each_move_is_preceded_by_a_notes_call_that_never_reaches_a_page_or_a_guesser(
    tmp_path: Path,
) -> None:
    from _mock_openrouter import CHAT_REPLY  # what the mock answers a plain (notes) call with

    rounds = 2
    seed, targets = distinct_target_seed(rounds, ["ai-1", "ai-2"])
    with mock_openrouter() as (mock_url, requests):
        env = {**LLM_ENV, "OPENROUTER_BASE_URL": mock_url}
        with web_server(tmp_path, "--players", players_file(tmp_path), "--think", env=env) as url:
            stream = Stream(url)
            stream.next()
            seats = [
                {"kind": "llm", "player": "Dry Sceptic"},
                {"kind": "llm", "player": "Bright Optimist"},
            ]
            assert post(url, "/api/start", seats=seats, rounds=rounds, seed=seed).status_code == 202
            while True:
                event, state = stream.next()
                if event == "state" and state["observation"]["phase"] is None:
                    break
            stream.close()

    moves = moves_of(requests)
    notes = plain_calls(requests)
    assert len(moves) == 2 * rounds and len(notes) == len(moves)  # one notes call per move
    assert sum(is_reaction(r) for r in requests) == rounds  # and one reaction per round
    for request in moves:  # the move was asked with the same model's notes in front of it
        assert CHAT_REPLY in json.dumps(observation_sent(request))
    for request in notes:
        text = str(request["messages"][-1]["content"])
        if "You are the guesser" in text:
            situation = json.loads(text.split("The situation:\n", 1)[1])
            assert "target" not in situation  # past rounds list revealed targets only
            assert all(r["round"] < situation["round"] for r in situation.get("past_rounds", []))
    # What a model wrote while thinking reaches a page only as a guesser's thoughts or, after the
    # reveal, as the psychic's reaction and notes; never in a state, talk or any other frame.
    for raw in stream.raw:
        if '"type": "thinking"' in raw or '"type": "reaction"' in raw:
            continue
        assert CHAT_REPLY not in raw


def test_with_needle_steps_the_guesser_moves_the_needle_in_public_steps_and_leaks_nothing(
    tmp_path: Path,
) -> None:
    from _mock_openrouter import CHAT_REPLY, STEP_GUESS, STEP_ONE, STEP_TWO
    from test_web import is_step

    rounds = 2
    seed, targets = distinct_target_seed(rounds, ["ai-1", "ai-2"])
    with mock_openrouter() as (mock_url, requests):
        env = {**LLM_ENV, "OPENROUTER_BASE_URL": mock_url}
        with web_server(tmp_path, "--needle-steps", "--think", env=env) as url:
            stream = Stream(url)
            stream.next()
            seats = [{"kind": "llm"}, {"kind": "llm"}]
            assert post(url, "/api/start", seats=seats, rounds=rounds, seed=seed).status_code == 202
            while True:
                event, state = stream.next()
                if event == "state" and state["observation"]["phase"] is None:
                    break
            stream.close()

    steps = [r for r in requests if is_step(r)]
    assert len(steps) == 2 * rounds  # two steps per guess: move, then lock
    for request in steps:  # a step is asked the guesser's allow-list and no target
        text = str(request["messages"][-1]["content"])
        if "You are the guesser" in text:
            situation = json.loads(text.split("The situation:\n", 1)[1].split("\n\nYou may", 1)[0])
            assert "target" not in situation
    frames = [json.loads(raw) for raw in stream.raw]
    thoughts = [f for f in frames if f.get("type") == "thinking"]
    assert [t["text"] for t in thoughts[:2]] == [STEP_ONE, STEP_TWO]
    drafts = [f for f in frames if f.get("type") == "draft" and f["value"] is not None]
    assert [(d["value"], d["final"]) for d in drafts[:2]] == [(40, False), (STEP_GUESS, True)]
    last = [f for f in frames if f.get("type") == "state"][-1]
    assert all(r["guess"] == STEP_GUESS for r in last["observation"]["history"])
    # the psychic notes (the mock plain reply) appear only in a reaction, never elsewhere
    for raw in stream.raw:
        if '"type": "reaction"' in raw or '"type": "thinking"' in raw:
            continue
        assert CHAT_REPLY not in raw
    assert all(str(t) not in json.dumps(thoughts) for t in targets[:1])


def test_the_call_cap_bounds_a_match_with_needle_steps(tmp_path: Path) -> None:
    with mock_openrouter() as (mock_url, requests):
        env = {**LLM_ENV, "OPENROUTER_BASE_URL": mock_url}
        with web_server(tmp_path, "--needle-steps", "--max-calls", "4", env=env) as url:
            stream = Stream(url)
            stream.next()
            seats = [{"kind": "llm"}, {"kind": "llm"}]
            assert post(url, "/api/start", seats=seats, rounds=6).status_code == 202
            while True:
                event, state = stream.next()
                if event == "problem":
                    break
            stream.close()
    assert "call limit" in state["reason"]
    assert len(requests) == 4  # steps count toward the cap like any call
