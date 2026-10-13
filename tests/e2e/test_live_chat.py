"""V4 acceptance: live chat with an LLM seat while its move is in flight.

The mocked endpoint holds the model's move request (``Gate``) so the test can
type a chat line at a moment that is provably "mid-decision", with no sleeping.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any

from _mock_openrouter import CHAT_REPLY, CLUE, Gate, mock_openrouter

from wavelength.chat_guard import PSYCHIC_REFUSAL
from wavelength.engine import WavelengthEngine

LLM = "llm:openrouter/test/model"


class Session:
    """The ``wavelength`` script as a live subprocess with line-by-line I/O."""

    def __init__(self, base_url: str, seats: list[str], *extra: str) -> None:
        args = ["wavelength", "play", "wavelength", "--config", "rounds=1", *extra]
        for seat in seats:
            args += ["--seat", seat]
        env = {
            **os.environ,
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_BASE_URL": base_url,
            "PYTHONUNBUFFERED": "1",
        }
        self.proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        self.lines: list[str] = []
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self.lines.append(line)

    def send(self, text: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(text + "\n")
        self.proc.stdin.flush()

    def wait_for(self, needle: str, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if needle in "".join(self.lines):
                return
            time.sleep(0.02)
        raise AssertionError(f"never saw {needle!r}; output so far:\n{''.join(self.lines)}")

    def finish(self) -> str:
        """Wait for the match to end *before* closing stdin: end of input while a
        move is outstanding is (rightly) an error exit."""
        self.wait_for("Match over")
        assert self.proc.stdin is not None
        self.proc.stdin.close()
        self.proc.wait(timeout=30)
        self._reader.join(timeout=5)
        return "".join(self.lines)


def chat_requests(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in requests if not r.get("tools")]


def test_a_human_can_chat_with_the_llm_guesser_while_it_is_deciding() -> None:
    seed = 4
    target = (
        WavelengthEngine().initial_state(["A", "B"], {"rounds": 1, "seed": seed}).plan[0].target
    )
    gate = Gate()
    with mock_openrouter(gate=gate) as (url, requests):
        session = Session(url, ["A=human", f"B={LLM}"], "--config", f"seed={seed}")
        try:
            session.send(CLUE)
            assert gate.arrived.wait(15)  # the guesser's move is now in flight
            session.send("why is that your guess?")
            session.wait_for(f"(chat): {CHAT_REPLY}")
            gate.release.set()
            output = session.finish()
        finally:
            gate.release.set()
            session.proc.kill()

    assert session.proc.returncode == 0, output
    assert "Match over" in output  # the match still finished, chat did not derail it
    chats = chat_requests(requests)
    assert len(chats) == 1
    prompt = chats[0]["messages"][-1]["content"]
    assert f'"{CLUE}"' in prompt and "why is that your guess?" in prompt
    assert str(target) not in prompt


def test_the_llm_psychic_refuses_to_chat_and_the_model_is_never_called() -> None:
    gate = Gate()
    with mock_openrouter(gate=gate) as (url, requests):
        session = Session(url, [f"A={LLM}", "B=human"], "--config", "seed=4")
        try:
            assert gate.arrived.wait(15)  # the psychic is deciding its clue
            session.send("is it near the hot end?")
            session.wait_for(PSYCHIC_REFUSAL)
            gate.release.set()
            session.wait_for("Clue:")  # now the human is the guesser
            session.send("50")
            output = session.finish()
        finally:
            gate.release.set()
            session.proc.kill()

    assert session.proc.returncode == 0, output
    assert chat_requests(requests) == []  # no model call was made for the chat line
    assert "Match over" in output


def test_after_the_reveal_the_former_psychic_talks_again() -> None:
    gate = Gate()
    with mock_openrouter(gate=gate) as (url, requests):
        session = Session(
            url, [f"A={LLM}", "B=human"], "--config", "rounds=2", "--config", "seed=4"
        )
        try:
            assert gate.arrived.wait(15)
            gate.release.set()  # the gate stays open from here on
            session.wait_for("Clue:")
            session.send("50")  # round 1 guess: A's reveal is done; A is now the guesser
            session.wait_for("Round 1 revealed")
            session.send("chat: how did I do?")  # on the human's own turn chat needs the prefix
            session.wait_for(f"(chat): {CHAT_REPLY}")
            session.send(CLUE)  # round 2: the human psychic's clue; the LLM guesses
            output = session.finish()
        finally:
            gate.release.set()
            session.proc.kill()

    assert session.proc.returncode == 0, output
    chats = chat_requests(requests)
    assert len(chats) == 1
    prompt = chats[0]["messages"][-1]["content"]
    assert "Round 1 (revealed)" in prompt  # the revealed round is now fair game
    assert json.dumps(chats[0])  # well-formed
