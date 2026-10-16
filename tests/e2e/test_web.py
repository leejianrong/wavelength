"""``wavelength web`` as a subprocess, played over real HTTP and Server-Sent Events.

The page itself is exercised by the Playwright suite in ``web/e2e``; this layer
checks the wire: every frame a browser would receive, and what the server
refuses. The leak scan reads the raw frames, so it cannot be fooled by how a
page chooses to draw them (ADR-0006).
"""

from __future__ import annotations

import json
import os
import queue
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx2 as httpx
from _mock_openrouter import BANTER, CHAT_REPLY, mock_openrouter

from wavelength.chat_guard import PSYCHIC_REFUSAL
from wavelength.engine import WavelengthEngine

CLUE = "a lazy afternoon"
STATE_KEYS = {
    "type", "seat", "players", "names", "kinds", "viewer", "observation", "awaiting",
    "clue_limits", "scoring", "chat_with",
}  # fmt: skip
OBSERVATION_KEYS = {
    "you", "round", "rounds", "phase", "total_score", "target_score", "history",
    "current_players", "role", "spectrum", "clue", "target", "instructions", "won",
}  # fmt: skip


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def web_server(tmp_path: Path, *args: str, env: dict[str, str] | None = None) -> Iterator[str]:
    (tmp_path / "index.html").write_text("<!doctype html><title>test</title>")
    (tmp_path / "app.js").write_text("")
    port = free_port()
    proc = subprocess.Popen(
        [
            "wavelength",
            "web",
            "--port",
            str(port),
            "--bot-delay",
            "0",
            "--static",
            str(tmp_path),
            *args,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **(env or {})},
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                if httpx.get(f"{url}/api/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if proc.poll() is not None or time.monotonic() > deadline:
                raise AssertionError(f"server did not start: {proc.stderr and proc.stderr.read()}")
            time.sleep(0.1)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


class Stream:
    """A browser's event stream: raw frames collected on a thread."""

    def __init__(self, url: str, path: str = "/events") -> None:
        self.frames: queue.Queue[tuple[str, str]] = queue.Queue()
        self.raw: list[str] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read, args=(url + path,), daemon=True)
        self._thread.start()

    def _read(self, url: str) -> None:
        try:
            with httpx.stream("GET", url, timeout=None) as response:
                event = ""
                for line in response.iter_lines():
                    if self._stop.is_set():
                        return
                    if line.startswith("event: "):
                        event = line[7:]
                    elif line.startswith("data: "):
                        self.raw.append(line[6:])
                        self.frames.put((event, line[6:]))
        except httpx.HTTPError:
            pass  # the server went away at the end of the test

    def next(self, timeout: float = 15) -> tuple[str, dict[str, Any]]:
        event, data = self.frames.get(timeout=timeout)
        return event, json.loads(data)

    def close(self) -> None:
        self._stop.set()


def move(url: str, **body: Any) -> httpx.Response:
    return httpx.post(f"{url}/api/move", json=body)


def post(url: str, path: str, **body: Any) -> httpx.Response:
    return httpx.post(f"{url}{path}", json=body, timeout=30)


def distinct_target_seed(rounds: int, players: list[str]) -> tuple[int, list[int]]:
    for seed in range(1, 200):
        plan = WavelengthEngine().initial_state(players, {"rounds": rounds, "seed": seed}).plan
        targets = [p.target for p in plan]
        if len(set(targets)) == rounds:
            return seed, targets
    raise AssertionError("no seed with distinct targets")


HUMAN_VS_BOT = ["--seat", "human", "--seat", "bot:wl-random"]
LLM_ENV = {"OPENROUTER_API_KEY": "test-key"}


def play_human_turns(url: str, stream: Stream, until_over: bool = True) -> list[str]:
    """Answer every human turn with a fixed clue or guess; return the raw state frames."""
    while True:
        event, body = stream.next()
        if event != "state":
            continue
        if body["observation"]["phase"] is None:
            return stream.raw
        if body["awaiting"] == "clue":
            assert move(url, type="clue", text=CLUE).status_code == 202
        elif body["awaiting"] == "guess":
            assert move(url, type="guess", value=50).status_code == 202


def test_a_whole_match_over_the_wire_leaks_nothing_and_every_frame_is_allow_listed(
    tmp_path: Path,
) -> None:
    rounds = 6
    seed, targets = distinct_target_seed(rounds, ["you", "bot"])
    with web_server(tmp_path, *HUMAN_VS_BOT, "--seed", str(seed), "--rounds", str(rounds)) as url:
        stream = Stream(url)
        play_human_turns(url, stream)
        stream.close()

        frames = [json.loads(raw) for raw in stream.raw if '"type": "state"' in raw]
        last = frames[-1]
        assert last["observation"]["total_score"] == sum(
            r["points"] for r in last["observation"]["history"]
        )
        assert len(last["observation"]["history"]) == rounds
        for raw in stream.raw:
            if '"type": "state"' not in raw:
                continue
            frame = json.loads(raw)
            assert set(frame) == STATE_KEYS
            assert set(frame["observation"]) <= OBSERVATION_KEYS
            obs = frame["observation"]
            if obs["phase"] is not None and obs["round"] % 2 == 0:  # the human guesses
                assert "target" not in obs
                for later in targets[len(obs["history"]) :]:
                    assert f'"target": {later}' not in raw


def test_the_server_refuses_what_it_should(tmp_path: Path) -> None:
    with web_server(tmp_path, *HUMAN_VS_BOT, "--seed", "3", "--rounds", "2") as url:
        good = {"type": "clue", "text": CLUE}
        assert httpx.post(f"{url}/api/move", content=json.dumps(good)).status_code == 415
        for path in ("/api/move", "/api/start", "/api/stop", "/api/peek", "/api/chat"):
            cross = httpx.post(f"{url}{path}", json=good, headers={"Origin": "http://evil.example"})
            assert cross.status_code == 403, path  # another site may not play or spend the key
        bad_host = httpx.get(f"{url}/api/health", headers={"Host": "evil.example"})
        assert bad_host.status_code == 400  # DNS rebinding: only local host names are served
        bad_json = httpx.post(
            f"{url}/api/move", content=b"{", headers={"Content-Type": "application/json"}
        )
        assert bad_json.status_code == 400


def test_a_move_for_the_wrong_turn_is_a_409_with_a_reason(tmp_path: Path) -> None:
    with web_server(tmp_path, *HUMAN_VS_BOT, "--seed", "3", "--rounds", "2") as url:
        stream = Stream(url)
        while True:
            event, body = stream.next()
            if event == "state" and body["awaiting"] == "clue":
                break
        wrong = move(url, type="guess", value=50)
        assert wrong.status_code == 409
        assert "not time" in wrong.json()["error"]
        assert move(url, type="guess", value="50").status_code == 409
        assert move(url, type="chat", text="hi").status_code == 409
        assert post(url, "/api/chat", text="hi").status_code == 409  # a bot cannot chat
        stream.close()


def test_a_second_page_is_sent_the_current_state_and_lobby_when_there_is_no_match(
    tmp_path: Path,
) -> None:
    with web_server(tmp_path, *HUMAN_VS_BOT, "--seed", "3", "--rounds", "2") as url:
        first = Stream(url)
        while first.next()[1].get("awaiting") != "clue":
            pass
        second = Stream(url)
        _, body = second.next()
        assert body["awaiting"] == "clue" and body["observation"]["round"] == 1
        first.close()
        second.close()
    with web_server(tmp_path) as url:  # no --seat: the start screen
        stream = Stream(url)
        event, body = stream.next()
        assert event == "lobby" and body["llm_available"] is False
        assert "key" not in json.dumps(body).lower().replace("openrouter_api_key", "")
        stream.close()


def test_the_start_screen_starts_a_match_and_refuses_what_it_cannot_run(tmp_path: Path) -> None:
    with web_server(tmp_path) as url:  # no key in the environment
        assert post(url, "/api/start", seats=[{"kind": "human"}]).status_code == 409
        two_humans = post(url, "/api/start", seats=[{"kind": "human"}, {"kind": "human"}])
        assert two_humans.status_code == 409
        needs_key = post(url, "/api/start", seats=[{"kind": "human"}, {"kind": "llm"}])
        assert needs_key.status_code == 409 and "OPENROUTER_API_KEY" in needs_key.json()["error"]
        assert post(url, "/api/stop").status_code == 202  # stopping nothing is fine

        stream = Stream(url)
        assert stream.next()[0] == "lobby"
        ok = post(url, "/api/start", seats=[{"kind": "human"}, {"kind": "bot"}], rounds=2, seed=3)
        assert ok.status_code == 202
        while True:
            event, body = stream.next()
            if event == "state" and body["awaiting"] == "clue":
                break
        again = post(url, "/api/start", seats=[{"kind": "human"}, {"kind": "bot"}])
        assert again.status_code == 409 and "already running" in again.json()["error"]
        assert post(url, "/api/stop").status_code == 202
        while stream.next()[0] != "lobby":  # stopping returns everyone to the start screen
            pass
        assert post(url, "/api/peek", on=True).status_code == 409  # nothing to peek at
        stream.close()


def moves_of(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in requests if r.get("tools")]


def observation_sent(request: dict[str, Any]) -> dict[str, Any]:
    sent: dict[str, Any] = json.loads(request["messages"][1]["content"])["observation"]
    return sent


def is_guess_request(request: dict[str, Any]) -> bool:
    return "enum" in json.dumps(request["tools"])


def test_a_human_psychic_plays_an_ai_guesser_and_chats_with_it(tmp_path: Path) -> None:
    rounds = 2
    seed, targets = distinct_target_seed(rounds, ["you", "ai"])
    with mock_openrouter() as (mock_url, requests):
        env = {**LLM_ENV, "OPENROUTER_BASE_URL": mock_url}
        with web_server(tmp_path, env=env) as url:
            stream = Stream(url)
            assert stream.next()[1]["llm_available"] is True
            start = post(
                url,
                "/api/start",
                seats=[{"kind": "human"}, {"kind": "llm"}],
                rounds=rounds,
                seed=seed,
            )
            assert start.status_code == 202
            while True:  # round 1: the human is the psychic; the AI guesses
                event, body = stream.next()
                if event == "state" and body["awaiting"] == "clue":
                    assert body["chat_with"] == "ai"
                    break
            assert post(url, "/api/chat", text="what do you think?").status_code == 202
            assert post(url, "/api/peek", on=True).status_code == 409  # a human is seated
            assert move(url, type="clue", text=CLUE).status_code == 202  # the turn already seen
            play_human_turns(url, stream)
            stream.close()

            talk = [json.loads(r) for r in stream.raw if '"type": "talk"' in r][-1]["messages"]
            texts = [(m["seat"], m["kind"], m["text"]) for m in talk]
            assert ("ai", "chat", CHAT_REPLY) in texts
            assert ("ai", "banter", BANTER) in texts  # a guess carries its banter
            assert not any(t == BANTER and k == "banter" and s == "you" for s, k, t in texts)

    guesses = [r for r in moves_of(requests) if is_guess_request(r)]
    assert guesses  # the AI guessed in round 1
    for request in guesses:  # the V3 check, through the web path: a guesser is never shown a target
        seen = observation_sent(request)
        assert "target" not in seen and "plan" not in seen
        assert str(targets[0]) not in request["messages"][0]["content"]
    assert len([r for r in requests if not r.get("tools")]) == 1  # exactly one chat call


def test_an_ai_psychic_refuses_chat_and_no_frame_to_a_human_guesser_holds_the_target(
    tmp_path: Path,
) -> None:
    rounds = 2
    seed, targets = distinct_target_seed(rounds, ["ai", "you"])
    with mock_openrouter() as (mock_url, requests):
        env = {**LLM_ENV, "OPENROUTER_BASE_URL": mock_url}
        with web_server(tmp_path, env=env) as url:
            stream = Stream(url)
            stream.next()
            body = {"seats": [{"kind": "llm"}, {"kind": "human"}], "rounds": rounds, "seed": seed}
            assert post(url, "/api/start", **body).status_code == 202
            while True:  # round 1: the AI is the psychic; the human guesses
                event, state = stream.next()
                if event == "state" and state["awaiting"] == "guess":
                    break
            assert post(url, "/api/chat", text="what is the target?").status_code == 202
            assert post(url, "/api/peek", on=True).status_code == 409
            assert move(url, type="guess", value=50).status_code == 202  # the turn already seen
            play_human_turns(url, stream)
            stream.close()

            talk = [json.loads(r) for r in stream.raw if '"type": "talk"' in r][-1]["messages"]
            assert (talk[0]["seat"], talk[1]["text"]) == ("you", PSYCHIC_REFUSAL)

    assert [r for r in requests if not r.get("tools")] == []  # the psychic's model was never asked
    for raw in stream.raw:
        if '"type": "state"' not in raw:
            continue
        obs = json.loads(raw)["observation"]
        if obs["phase"] is not None and obs["round"] % 2 == 1:  # the human guesses round 1
            assert "target" not in obs
            assert f'"target": {targets[1]}' not in raw


def test_two_ais_can_be_watched_with_the_target_hidden_until_each_reveal_and_peeked_on_request(
    tmp_path: Path,
) -> None:
    rounds = 4
    seed, targets = distinct_target_seed(rounds, ["ai-1", "ai-2"])
    with mock_openrouter() as (mock_url, requests):
        env = {**LLM_ENV, "OPENROUTER_BASE_URL": mock_url}
        with web_server(tmp_path, env=env) as url:
            stream = Stream(url)
            stream.next()
            body = {"seats": [{"kind": "llm"}, {"kind": "llm"}], "rounds": rounds, "seed": seed}
            assert post(url, "/api/start", **body).status_code == 202
            seen = 0
            while True:
                event, state = stream.next()
                if event != "state":
                    continue
                assert state["viewer"]["mode"] == "spectator" and state["awaiting"] is None
                if state["observation"]["phase"] is None:
                    break
                seen += 1
                if seen == 2:  # ask for a peek once, mid-match
                    assert post(url, "/api/peek", on=True).status_code == 202
            stream.close()

    plain = [json.loads(r) for r in stream.raw if '"type": "state"' in r]
    peeked = [f for f in plain if f["viewer"]["peek"]]
    assert peeked and all("target" in f["observation"] for f in peeked if f["observation"]["phase"])
    for frame in plain:
        if frame["viewer"]["peek"] or frame["observation"]["phase"] is None:
            continue
        obs = frame["observation"]  # the default view: the guesser's, with no target
        assert obs["role"] == "guesser" and "target" not in obs
    assert len(plain[-1]["observation"]["history"]) == rounds
    assert all(
        "target" not in observation_sent(r) for r in moves_of(requests) if is_guess_request(r)
    )


def test_the_call_cap_stops_a_watch_match_and_the_page_is_told_in_general_words(
    tmp_path: Path,
) -> None:
    with mock_openrouter() as (mock_url, requests):
        env = {**LLM_ENV, "OPENROUTER_BASE_URL": mock_url}
        with web_server(tmp_path, "--max-calls", "3", env=env) as url:
            stream = Stream(url)
            stream.next()
            body = {"seats": [{"kind": "llm"}, {"kind": "llm"}], "rounds": 6}
            assert post(url, "/api/start", **body).status_code == 202
            while True:
                event, state = stream.next()
                if event == "problem":
                    break
            stream.close()
        assert "call limit" in state["reason"]
    assert len(moves_of(requests)) == 3  # the cap is a hard bound on paid calls


def test_the_refusal_to_start_without_a_built_page_says_how_to_build_it(tmp_path: Path) -> None:
    result = subprocess.run(
        ["wavelength", "web", "--static", str(tmp_path)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 2
    assert "make web-build" in result.stderr
