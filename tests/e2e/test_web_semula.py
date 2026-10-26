"""An agent answering through semula (ADR-0014) over the wire.

The mock OpenRouter stands in for semula: it speaks the same API, so what the agent's seat sends
is what an agent would be asked. Checked: the address and key stay on the server, the call goes to
the project's path, the agent is asked one move at a time and never sees the target.
"""

from __future__ import annotations

import json
from pathlib import Path

from _mock_openrouter import mock_openrouter
from test_web import (
    Stream,
    distinct_target_seed,
    is_guess_request,
    is_reaction,
    moves_of,
    observation_sent,
    plain_calls,
    play_human_turns,
    post,
    web_server,
)

NO_KEY = {"OPENROUTER_API_KEY": ""}
AGENT = {"kind": "llm", "player": "Claude Code"}


def test_the_agent_player_is_offered_only_with_semula_and_needs_no_key(tmp_path: Path) -> None:
    with web_server(tmp_path, env=NO_KEY) as url:  # no --semula: no agent
        stream = Stream(url)
        lobby = stream.next()[1]
        stream.close()
        assert lobby["players"] == [] and lobby["agent_available"] is False
        refused = post(url, "/api/start", seats=[{"kind": "human"}, AGENT])
        assert refused.status_code in (400, 409)
    with web_server(tmp_path, "--semula", "http://127.0.0.1:9", env=NO_KEY) as url:
        stream = Stream(url)
        lobby = stream.next()[1]
        stream.close()
        assert lobby["llm_available"] is False and lobby["agent_available"] is True
        assert lobby["players"] == [
            {"name": "Claude Code", "model": "agent/claude-code", "agent": True}
        ]
        for raw in stream.raw:  # the address is operator config
            assert "127.0.0.1:9" not in raw and "semula-local" not in raw
        two = post(url, "/api/start", seats=[AGENT, AGENT])
        assert two.status_code in (400, 409) and "one agent" in two.text
        model = post(url, "/api/start", seats=[{"kind": "human"}, {"kind": "llm"}])
        assert model.status_code in (400, 409) and "OPENROUTER_API_KEY" in model.text


def test_an_agent_guesser_gets_one_move_call_a_turn_at_its_project_and_never_the_target(
    tmp_path: Path,
) -> None:
    rounds = 2
    seed, targets = distinct_target_seed(rounds, ["you", "ai"])
    with mock_openrouter() as (mock_url, requests):
        flags = ("--semula", mock_url, "--semula-project", "game", "--think", "--needle-steps")
        with web_server(tmp_path, *flags, env=NO_KEY) as url:
            stream = Stream(url)
            stream.next()
            seats = [{"kind": "human"}, AGENT]
            assert post(url, "/api/start", seats=seats, rounds=rounds, seed=seed).status_code == 202
            play_human_turns(url, stream)
            stream.close()
            states = [json.loads(r) for r in stream.raw if '"type": "state"' in r]
            assert all(s["agents"] == {"ai": 300.0} for s in states)
            assert all(s["kinds"]["ai"] == "llm" for s in states)
            for raw in stream.raw:
                assert mock_url not in raw and "semula-local" not in raw

    assert requests and set(requests.paths) == {"/v1/projects/game/chat/completions"}
    # notes and needle steps are off for an agent: every call is a move, or a psychic's reaction
    assert all(is_reaction(r) for r in plain_calls(requests))
    for request in moves_of(requests):
        if is_guess_request(request):
            assert "target" not in observation_sent(request)
            for target in targets:
                assert f'"target": {target}' not in json.dumps(request)


def test_a_move_the_agent_does_not_answer_in_time_ends_the_match_without_the_error_text(
    tmp_path: Path,
) -> None:
    seed, _ = distinct_target_seed(1, ["you", "ai"])
    with mock_openrouter(delay=4) as (mock_url, _):
        flags = ("--semula", mock_url, "--semula-timeout", "1")
        with web_server(tmp_path, *flags, env=NO_KEY) as url:
            stream = Stream(url)
            stream.next()
            seats = [{"kind": "human"}, AGENT]
            assert post(url, "/api/start", seats=seats, rounds=1, seed=seed).status_code == 202
            while True:
                event, body = stream.next(timeout=30)
                if event == "state" and body["awaiting"] == "clue":
                    post(url, "/api/move", type="clue", text="a lazy afternoon")
                if event == "problem":
                    break
            stream.close()
        assert mock_url not in body["reason"] and "Timeout" not in body["reason"]
