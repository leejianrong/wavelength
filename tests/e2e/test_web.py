"""``wavelength web`` as a subprocess, played over real HTTP and Server-Sent Events.

The page itself is exercised by the Playwright suite in ``web/e2e``; this layer
checks the wire: every frame a browser would receive, and what the server
refuses. The leak scan reads the raw frames, so it cannot be fooled by how a
page chooses to draw them (ADR-0006).
"""

from __future__ import annotations

import json
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

from wavelength.engine import WavelengthEngine

CLUE = "a lazy afternoon"
STATE_KEYS = {"type", "seat", "players", "observation", "awaiting", "clue_limits", "scoring"}
OBSERVATION_KEYS = {
    "you", "round", "rounds", "phase", "total_score", "target_score", "history",
    "current_players", "role", "spectrum", "clue", "target", "instructions", "won",
}  # fmt: skip


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def web_server(tmp_path: Path, *args: str) -> Iterator[str]:
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


def distinct_target_seed(rounds: int) -> tuple[int, list[int]]:
    for seed in range(1, 200):
        plan = (
            WavelengthEngine().initial_state(["you", "bot"], {"rounds": rounds, "seed": seed}).plan
        )
        targets = [p.target for p in plan]
        if len(set(targets)) == rounds:
            return seed, targets
    raise AssertionError("no seed with distinct targets")


def test_a_whole_match_over_the_wire_leaks_nothing_and_every_frame_is_allow_listed(
    tmp_path: Path,
) -> None:
    rounds = 6
    seed, targets = distinct_target_seed(rounds)
    with web_server(tmp_path, "--seed", str(seed), "--rounds", str(rounds)) as url:
        stream = Stream(url)
        last: dict[str, Any] = {}
        while True:
            event, body = stream.next()
            if event != "state":
                continue
            last = body
            obs = body["observation"]
            if obs["phase"] is None:
                break
            if body["awaiting"] == "clue":
                assert move(url, type="clue", text=CLUE).status_code == 202
            elif body["awaiting"] == "guess":
                assert move(url, type="guess", value=50).status_code == 202
        stream.close()

        assert last["observation"]["total_score"] == sum(
            r["points"] for r in last["observation"]["history"]
        )
        assert len(last["observation"]["history"]) == rounds
        for raw in stream.raw:
            frame = json.loads(raw)
            assert set(frame) == STATE_KEYS
            assert set(frame["observation"]) <= OBSERVATION_KEYS
            obs = frame["observation"]
            if obs["phase"] is not None and obs["round"] % 2 == 0:  # the human guesses
                assert "target" not in obs
                for later in targets[len(obs["history"]) :]:
                    assert f'"target": {later}' not in raw


def test_the_server_refuses_what_it_should(tmp_path: Path) -> None:
    with web_server(tmp_path, "--seed", "3", "--rounds", "2") as url:
        good = {"type": "clue", "text": CLUE}
        assert (
            httpx.get(f"{url}/events?seat=bot", timeout=3).status_code == 404
        )  # not a seat to watch
        assert httpx.post(f"{url}/api/move", content=json.dumps(good)).status_code == 415
        cross = httpx.post(f"{url}/api/move", json=good, headers={"Origin": "http://evil.example"})
        assert cross.status_code == 403
        bad_host = httpx.get(f"{url}/api/health", headers={"Host": "evil.example"})
        assert bad_host.status_code == 400  # DNS rebinding: only local host names are served
        assert (
            httpx.post(
                f"{url}/api/move", content=b"{", headers={"Content-Type": "application/json"}
            ).status_code
            == 400
        )


def test_a_move_for_the_wrong_turn_is_a_409_with_a_reason(tmp_path: Path) -> None:
    with web_server(tmp_path, "--seed", "3", "--rounds", "2") as url:
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
        assert move(url, seat="bot", type="clue", text=CLUE).status_code == 409
        stream.close()


def test_a_second_page_for_the_same_seat_is_sent_the_current_state(tmp_path: Path) -> None:
    with web_server(tmp_path, "--seed", "3", "--rounds", "2") as url:
        first = Stream(url)
        while first.next()[1]["awaiting"] != "clue":
            pass
        second = Stream(url)
        _, body = second.next()
        assert body["awaiting"] == "clue" and body["observation"]["round"] == 1
        first.close()
        second.close()


def test_the_refusal_to_start_without_a_built_page_says_how_to_build_it(tmp_path: Path) -> None:
    result = subprocess.run(
        ["wavelength", "web", "--static", str(tmp_path)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 2
    assert "make web-build" in result.stderr
