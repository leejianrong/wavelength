"""Voice through a fake vikaki hub: a plain WebSocket server on a thread that answers like the
real one. No Node, no voice, no network. What the tap sends is scanned for a leak."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any

import pytest
from agent_game_framework.core import SeatDecision, TextTurn, is_free_text
from websockets.asyncio.server import ServerConnection, serve

from wavelength.bots import RandomWavelengthBot
from wavelength.chat_guard import PSYCHIC_REFUSAL
from wavelength.seats import guard
from wavelength.voice import VoiceTap
from wavelength.web.broadcast import Broadcaster, Subscriber
from wavelength.web.session import WebSession

WAIT = 15.0
# Everything the tap may put on the wire. Anything else (a target, a plan, an observation) fails.
HELLO_KEYS = {"protocol_version", "type", "role", "client", "seats", "token", "session_id"}
SAY_KEYS = {"protocol_version", "type", "seat_id", "utterance_id", "text", "emotion", "kind"}
REACT_KEYS = {"protocol_version", "type", "seat_id", "emotion", "gesture", "seconds"}
TURN_KEYS = {"protocol_version", "type", "seat_id"}
ALLOWED = {
    "hello": HELLO_KEYS,
    "utterance": SAY_KEYS,
    "react": REACT_KEYS,
    "turn_started": TURN_KEYS,
    "turn_ended": TURN_KEYS,
    "cancel": {"protocol_version", "type", "utterance_id"},
}


class FakeHub:
    """Speaks every line: ``speech_started`` at once, ``speech_finished`` after ``speak_for``
    seconds (never, with ``None``). Records what arrives, with times."""

    def __init__(self, speak_for: float | None = 0.0, personas: list[str] | None = None) -> None:
        self.speak_for = speak_for
        self.personas = personas
        self.received: list[dict[str, Any]] = []
        self._conns: list[ServerConnection] = []
        self.finished_at: dict[str, float] = {}
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        threading.Thread(target=self._main, daemon=True).start()
        assert self._ready.wait(10)

    def _main(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self) -> None:
        async def handler(ws: ServerConnection) -> None:
            self._conns.append(ws)
            async for raw in ws:
                msg = json.loads(raw)
                self.received.append(msg)
                if msg["type"] == "hello":
                    welcome: dict[str, Any] = {
                        "protocol_version": 1,
                        "type": "welcome",
                        "role": msg.get("role", "driver"),
                    }
                    if self.personas is not None:
                        welcome["personas"] = self.personas
                    await ws.send(json.dumps(welcome))
                elif msg["type"] == "utterance":
                    uid, seat = msg["utterance_id"], msg["seat_id"]
                    await ws.send(
                        json.dumps({"type": "speech_started", "utterance_id": uid, "seat_id": seat})
                    )
                    if self.speak_for is not None:
                        self._loop.create_task(self._finish(ws, uid))
                elif msg["type"] == "cancel" and msg.get("utterance_id"):
                    await ws.send(
                        json.dumps(
                            {
                                "type": "speech_interrupted",
                                "utterance_id": msg["utterance_id"],
                                "reason": "cancelled",
                            }
                        )
                    )

        async with serve(handler, "127.0.0.1", 0) as server:
            self.port = server.sockets[0].getsockname()[1]
            self._ready.set()
            await asyncio.Event().wait()

    async def _finish(self, ws: ServerConnection, uid: str) -> None:
        await asyncio.sleep(self.speak_for or 0)
        self.finished_at[uid] = time.monotonic()
        try:
            await ws.send(json.dumps({"type": "speech_finished", "utterance_id": uid}))
        except Exception:  # noqa: BLE001 - the client left first
            pass

    def drop(self) -> None:
        """Close every connection from the hub's side, as a crashed hub would."""
        for ws in list(self._conns):
            asyncio.run_coroutine_threadsafe(ws.close(), self._loop).result(5)

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/ws"

    def sent(self, kind: str) -> list[dict[str, Any]]:
        return [m for m in self.received if m["type"] == kind]


def make_session(
    url: str,
    controllers: dict[str, Any],
    *,
    human: str | None = None,
    timeout: float = 5.0,
    rounds: int = 2,
    players: list[str] | None = None,
    voices: dict[str, str] | None = None,
) -> tuple[WebSession, Subscriber]:
    broadcaster = Broadcaster()
    ids = players or ["ai-1", "ai-2"]
    session = WebSession(
        ids,
        controllers,
        broadcaster=broadcaster,
        human=human,
        rounds=rounds,
        seed=5,
        voice_hub="http://127.0.0.1:8787",
        voices=voices,
        voice_connect=lambda players, voices, on_line, on_status: VoiceTap.connect(
            url, players, voices, timeout=timeout, on_line=on_line, on_status=on_status
        ),
    )
    return session, broadcaster.subscribe()


def events_until_over(sub: Subscriber) -> list[tuple[str, dict[str, Any]]]:
    seen: list[tuple[str, dict[str, Any]]] = []
    while True:
        event, data = sub.get(WAIT)
        body = json.loads(data)
        seen.append((event, body))
        if event == "state" and body["observation"]["phase"] is None:
            return seen


class Talker:
    def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
        if is_free_text(legal_actions):
            return SeatDecision(action="a lazy afternoon")
        return SeatDecision(action=40, banter="my gut says left of middle")

    def respond(self, history: Any, incoming: Any) -> TextTurn:
        return TextTurn(text="toward the heavy end, I think")


def test_a_whole_match_is_spoken_and_nothing_but_public_text_reaches_the_hub() -> None:
    hub = FakeHub()
    session, sub = make_session(hub.url, {"ai-1": Talker(), "ai-2": Talker()})
    session.start()
    seen = events_until_over(sub)
    session.join(WAIT)
    deadline = time.monotonic() + 5
    while len(hub.sent("react")) < 4 and time.monotonic() < deadline:
        time.sleep(0.02)  # the hub records the last messages a moment after they were sent

    # Every message is one of the known kinds with only its allowed keys.
    assert hub.received, "nothing was sent"
    for msg in hub.received:
        assert msg["type"] in ALLOWED, msg
        assert set(msg) <= ALLOWED[msg["type"]], msg
    # Two drivers, one per seat, each bound to its own hub seat.
    hellos = [h for h in hub.sent("hello") if h.get("role", "driver") == "driver"]
    assert sorted(h["seats"][0]["seat_id"] for h in hellos) == ["seat-1", "seat-2"]
    # The spoken text is the clue and the guesser's banter, and the clue is neutral.
    said = hub.sent("utterance")
    assert {m["kind"] for m in said} == {"clue", "banter"}
    assert {m["text"] for m in said} == {"a lazy afternoon", "my gut says left of middle"}
    assert all(m["emotion"] == "neutral" for m in said if m["kind"] == "clue")
    # Faces after each reveal: silent reactions from the points, nothing else.
    assert len(hub.sent("react")) == 4  # two rounds, both seats
    wire = json.dumps(hub.received)
    for forbidden in ("target", "plan", "observation", "history", "spectrum"):
        assert forbidden not in wire
    # The page hears the voice status and the line being spoken.
    voice_events = [b for e, b in seen if e == "voice"]
    assert voice_events and voice_events[0]["status"] == "on"
    assert any(v["line"] and v["line"]["kind"] == "clue" for v in voice_events)
    assert all(set(v) == {"type", "status", "line", "seats"} for v in voice_events)


def test_the_reveal_waits_for_the_clue_to_finish_being_spoken() -> None:
    hub = FakeHub(speak_for=0.6)
    session, sub = make_session(hub.url, {"ai-1": Talker(), "ai-2": Talker()}, rounds=1)
    session.start()
    reveal_at = 0.0
    while True:
        event, data = sub.get(WAIT)
        body = json.loads(data)
        if event == "state" and body["observation"]["history"]:
            reveal_at = time.monotonic()
            break
    session.join(WAIT)
    clue_ids = [m["utterance_id"] for m in hub.sent("utterance") if m["kind"] == "clue"]
    assert clue_ids and hub.finished_at[clue_ids[0]] <= reveal_at


def test_a_hub_that_never_finishes_a_line_does_not_stall_the_match() -> None:
    hub = FakeHub(speak_for=None)
    session, sub = make_session(
        hub.url, {"ai-1": Talker(), "ai-2": Talker()}, timeout=0.3, rounds=1
    )
    session.start()
    events_until_over(sub)
    session.join(WAIT)
    assert hub.sent("cancel"), "a line that never finished should be cancelled"


def test_no_hub_means_a_text_game_and_a_voice_off_status() -> None:
    session, sub = make_session("ws://127.0.0.1:9/ws", {"ai-1": Talker(), "ai-2": Talker()})
    session.start()
    seen = events_until_over(sub)
    session.join(WAIT)
    statuses = [b["status"] for e, b in seen if e == "voice"]
    assert statuses and statuses[-1] == "off"
    assert seen[-1][1]["observation"]["phase"] is None


def test_a_hub_that_dies_mid_match_switches_the_voice_off_and_play_goes_on() -> None:
    hub = FakeHub(speak_for=0.3)
    session, sub = make_session(hub.url, {"ai-1": Talker(), "ai-2": Talker()}, rounds=3)
    session.start()
    hub.drop()
    seen = events_until_over(sub)
    session.join(WAIT)
    assert [b["status"] for e, b in seen if e == "voice"][-1] == "off"


def test_a_human_psychics_clue_and_the_ai_partners_chat_reply_are_spoken() -> None:
    hub = FakeHub()
    session, sub = make_session(
        hub.url, {"ai": guard(Talker())}, human="you", players=["you", "ai"], rounds=1
    )
    session.start()
    while True:
        event, data = sub.get(WAIT)
        body = json.loads(data)
        if event == "state" and body["awaiting"] == "clue":
            break
    session.chat("what do you make of it?")
    deadline = time.monotonic() + 5
    while not hub.sent("utterance") and time.monotonic() < deadline:
        time.sleep(0.02)  # the hub records what it was sent a moment after the client sent it
    kinds = [m["kind"] for m in hub.sent("utterance")]
    assert kinds == ["table_talk"]
    assert hub.sent("utterance")[0]["text"] == "toward the heavy end, I think"
    session.close()


def test_an_ai_psychics_chat_refusal_is_never_spoken() -> None:
    hub = FakeHub()
    gate = threading.Event()

    class Slow(Talker):
        def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
            gate.wait(WAIT)
            return super().decide(observation, legal_actions)

    session, sub = make_session(
        hub.url, {"ai": guard(Slow())}, human="you", players=["ai", "you"], rounds=1
    )
    session.start()  # the AI is the psychic and is "thinking"
    session.chat("what is the target?")
    time.sleep(0.3)  # long enough for a line, had one been sent, to arrive
    assert PSYCHIC_REFUSAL not in json.dumps(hub.received)
    assert hub.sent("utterance") == []
    gate.set()
    session.close()


def test_a_clue_turn_never_speaks_banter() -> None:
    class Banterer(Talker):
        def decide(self, observation: Any, legal_actions: list[Any]) -> SeatDecision[Any]:
            if is_free_text(legal_actions):
                return SeatDecision(action="a lazy afternoon", banter="SECRET target is high")
            return SeatDecision(action=40, banter="my gut says left of middle")

    hub = FakeHub()
    session, sub = make_session(hub.url, {"ai-1": Banterer(), "ai-2": Banterer()}, rounds=1)
    session.start()
    events_until_over(sub)
    session.join(WAIT)
    assert "SECRET" not in json.dumps(hub.received)


def test_a_session_without_voice_has_no_voice_events_and_no_hub_address() -> None:
    broadcaster = Broadcaster()
    session = WebSession(
        ["a", "b"],
        {"a": RandomWavelengthBot(), "b": RandomWavelengthBot()},
        broadcaster=broadcaster,
        rounds=1,
        seed=5,
    )
    sub = broadcaster.subscribe()
    session.start()
    seen = events_until_over(sub)
    assert not [e for e, _ in seen if e == "voice"]
    assert all(b["voice_hub"] is None for e, b in seen if e == "state")


@pytest.mark.parametrize("n", [1])
def test_the_tap_is_a_noop_when_off(n: int) -> None:
    tap = VoiceTap({}, {"a": "seat-1"})
    tap.clue("a", "hello")
    tap.reply("a", "hi")
    tap.reveal("a", "b", 3, 4)
    tap.wait()
    assert not tap.active


def driver_seats(hub: FakeHub) -> dict[str, str | None]:
    """Hub seat id to the persona each driver bound (viewers' probes are not drivers)."""
    return {
        h["seats"][0]["seat_id"]: h["seats"][0].get("persona")
        for h in hub.sent("hello")
        if h.get("role") == "driver"
    }


def run_to_the_end(session: WebSession, sub: Subscriber) -> list[tuple[str, dict[str, Any]]]:
    session.start()
    seen = events_until_over(sub)
    session.join(WAIT)
    return seen


def test_a_named_players_persona_is_bound_to_its_seat_and_the_page_is_told() -> None:
    hub = FakeHub(personas=["ada", "ben", "cy"])
    session, sub = make_session(
        hub.url, {"ai-1": Talker(), "ai-2": Talker()}, rounds=1, voices={"ai-2": "cy"}
    )
    seen = run_to_the_end(session, sub)
    # ai-2 asked for cy; ai-1 named none and gets the first persona nobody else has.
    assert driver_seats(hub) == {"seat-1": "ada", "seat-2": "cy"}
    voice = next(b for e, b in seen if e == "voice" and b["status"] == "on")
    assert voice["seats"] == ["ada", "cy"]


def test_two_seats_never_end_up_with_the_same_face() -> None:
    hub = FakeHub(personas=["ada", "ben"])
    session, sub = make_session(
        hub.url, {"ai-1": Talker(), "ai-2": Talker()}, rounds=1, voices={"ai-1": "ben"}
    )
    run_to_the_end(session, sub)
    assert driver_seats(hub) == {"seat-1": "ben", "seat-2": "ada"}


def test_a_persona_the_hub_does_not_have_falls_back_instead_of_turning_the_voice_off() -> None:
    hub = FakeHub(personas=["ada", "ben"])
    session, sub = make_session(
        hub.url, {"ai-1": Talker(), "ai-2": Talker()}, rounds=1, voices={"ai-1": "nobody"}
    )
    seen = run_to_the_end(session, sub)
    assert driver_seats(hub) == {"seat-1": "ada", "seat-2": "ben"}
    assert [b["status"] for e, b in seen if e == "voice"][-1] == "on"


def test_a_hub_with_no_personas_file_leaves_every_seat_to_its_default() -> None:
    hub = FakeHub(personas=None)
    session, sub = make_session(
        hub.url, {"ai-1": Talker(), "ai-2": Talker()}, rounds=1, voices={"ai-1": "ada"}
    )
    seen = run_to_the_end(session, sub)
    assert driver_seats(hub) == {"seat-1": None, "seat-2": None}
    voice = next(b for e, b in seen if e == "voice" and b["status"] == "on")
    assert voice["seats"] == [None, None]


def test_the_psychic_is_silent_between_its_clue_and_the_reveal_and_notes_never_reach_the_hub() -> (
    None
):
    """V13 (ADR-0011): the guesser thinks aloud, the psychic's avatar does nothing until the
    faces come with the reveal, and then it says one reaction line. Its notes stay off the wire."""
    from test_web_thinking import GUESSER_NOTES, REACTION, FakeBackend

    from wavelength.thinking import ThinkingSeat

    hub = FakeHub()
    seats = {p: guard(ThinkingSeat(FakeBackend())) for p in ("ai-1", "ai-2")}  # type: ignore[arg-type]
    session, sub = make_session(hub.url, seats)
    session.kinds = {"ai-1": "llm", "ai-2": "llm"}
    session.start()
    events_until_over(sub)
    session.join(WAIT)
    deadline = time.monotonic() + 5
    while len(hub.sent("utterance")) < 8 and time.monotonic() < deadline:
        time.sleep(0.02)

    wire = json.dumps(hub.received)
    assert "NOTES-PSY" not in wire
    said = hub.sent("utterance")
    assert {m["text"] for m in said} >= {GUESSER_NOTES[:60], REACTION} or any(
        GUESSER_NOTES in m["text"] for m in said
    )
    for msg in hub.received:  # still only the known kinds and keys
        assert msg["type"] in ALLOWED and set(msg) <= ALLOWED[msg["type"]], msg
    assert {m["kind"] for m in said} <= {"clue", "banter"}

    flow = [m for m in hub.received if m["type"] in ("utterance", "react", "turn_started")]
    for i, clue in enumerate(flow):
        if clue["type"] != "utterance" or clue["kind"] != "clue":
            continue
        psychic = clue["seat_id"]
        for later in flow[i + 1 :]:
            if later["type"] == "react":
                break
            assert later["seat_id"] != psychic, f"the psychic stirred before the reveal: {later}"


def test_a_needle_step_is_spoken_in_the_guessers_voice_and_the_psychic_stays_silent() -> None:
    """V15 (ADR-0012): each step's line goes to the guesser's driver, one at a time, nothing of
    the psychic's notes reaches the hub, and the psychic does nothing between clue and reveal."""
    import json as _json

    from test_web_thinking import StepBackend

    from wavelength.needle_seat import NeedleSeat

    hub = FakeHub()
    seats = {p: guard(NeedleSeat(StepBackend())) for p in ("ai-1", "ai-2")}  # type: ignore[arg-type]
    session, sub = make_session(hub.url, seats)
    session.kinds = {"ai-1": "llm", "ai-2": "llm"}
    session.start()
    events_until_over(sub)
    session.join(WAIT)
    deadline = time.monotonic() + 5
    while len(hub.sent("utterance")) < 10 and time.monotonic() < deadline:
        time.sleep(0.02)

    said = hub.sent("utterance")
    texts = [m["text"] for m in said]
    assert texts.count("It sounds calm.") == 2 and texts.count("A touch calmer.") == 2
    assert "NOTES-PSY" not in _json.dumps(hub.received)
    for msg in hub.received:
        assert msg["type"] in ALLOWED and set(msg) <= ALLOWED[msg["type"]], msg
    flow = [m for m in hub.received if m["type"] in ("utterance", "react")]
    for i, clue in enumerate(flow):
        if clue["type"] != "utterance" or clue["kind"] != "clue":
            continue
        for later in flow[i + 1 :]:
            if later["type"] == "react":
                break
            assert later["seat_id"] != clue["seat_id"], f"the psychic spoke early: {later}"
