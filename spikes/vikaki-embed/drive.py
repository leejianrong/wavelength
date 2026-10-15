"""Spike driver: speaks a line for seat-1 and seat-2, then cancels a third mid-line.

Prints one JSON line per measurement. Run:
uv run --with <vikaki>/clients/python python drive.py [--hub ws://...] [--only first]
"""

import argparse
import json
import time

from vikaki_client import Vikaki

p = argparse.ArgumentParser()
p.add_argument("--hub", default="ws://127.0.0.1:8787/ws")
p.add_argument("--only", choices=["first", "all"], default="all")
args = p.parse_args()

events: list[dict] = []
t0 = time.monotonic()


def out(**kw) -> None:
    print(json.dumps({"t": round(time.monotonic() - t0, 3), **kw}), flush=True)


with Vikaki(args.hub) as v:
    v.on_event(lambda e: events.append({"t": time.monotonic(), **e}))
    lines = [("seat-1", "Something you would find on a beach."), ("seat-2", "A sandcastle, maybe?")]
    if args.only == "first":
        lines = lines[:1]
    for seat, text in lines:
        sent = time.monotonic()
        v.turn_started(seat)
        uid = v.say(text, seat_id=seat)
        done = v.wait_finished(uid, timeout=60)
        started = next(
            (
                e
                for e in events
                if e.get("type") == "speech_started" and e.get("utterance_id") == uid
            ),
            None,
        )
        out(
            seat=seat,
            uid=uid,
            result=done.get("type"),
            to_started_s=round(started["t"] - sent, 3) if started else None,
            to_finished_s=round(time.monotonic() - sent, 3),
        )
        v.turn_ended(seat)
    if args.only == "all":
        uid = v.say(
            "This is a long line that I am going to cancel in the middle of it.", seat_id="seat-1"
        )
        time.sleep(0.4)
        sent = time.monotonic()
        v.cancel(uid)
        done = v.wait_finished(uid, timeout=10)
        out(
            cancel=True,
            result=done.get("type"),
            cancel_to_event_s=round(time.monotonic() - sent, 3),
        )
