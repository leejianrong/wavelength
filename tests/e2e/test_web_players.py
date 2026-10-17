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
    move,
    moves_of,
    observation_sent,
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
                {"name": "Dry Sceptic", "model": "test/sceptic"},
                {"name": "Bright Optimist", "model": "test/optimist"},
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
        with web_server(tmp_path, "--players", players_file(tmp_path), env=env) as url:
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

    chats = [r for r in requests if not r.get("tools")]
    assert len(chats) == 1  # only the guesser-round chat; the psychic's model was never asked
    assert SKEPTIC in system_of(chats[0])
