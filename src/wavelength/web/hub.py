"""The vikaki hub for ``wavelength web --voice``: where it is, and (optionally) starting it.

The page frames the hub's avatar page, and this server's drivers speak to its WebSocket. The
hub only answers local ``Host`` names, so the address must be ``127.0.0.1``, ``localhost`` or
``[::1]``; the hub must also list this server's origin to allow framing (vikaki ``docs/embed.md``).
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

from wavelength.web.app import LOCAL_HOSTS
from wavelength.web.host import VoiceConfig

DEFAULT_HUB = "http://127.0.0.1:8787"
PERSONAS = "personas.table.example.yaml"


class HubError(ValueError):
    """The hub address or checkout is unusable; the message says what to fix."""


def voice_config(hub: str, token: str | None = None) -> VoiceConfig:
    parts = urlsplit(hub)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
        or parts.username
    ):
        raise HubError(f"--hub must be a bare origin such as {DEFAULT_HUB}, not {hub!r}")
    shown = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    if shown not in LOCAL_HOSTS:
        raise HubError(
            f"--hub must use 127.0.0.1, localhost or [::1] (the hub refuses other Host names), "
            f"not {parts.hostname!r}"
        )
    port = parts.port or (443 if parts.scheme == "https" else 80)
    origin = f"{parts.scheme}://{shown}:{port}"
    ws = f"{'wss' if parts.scheme == 'https' else 'ws'}://{shown}:{port}/ws"
    return VoiceConfig(ws_url=ws, http_origin=origin, token=token)


def start_hub(
    vikaki_dir: Path, config: VoiceConfig, *, tts: str, frame_origins: list[str]
) -> subprocess.Popen[bytes]:
    """Run ``pnpm serve`` in a vikaki checkout (built, with ``make install-voice`` for ``kokoro``)
    and wait for its port. ``tts`` is ``fake`` or ``kokoro``."""
    if not (vikaki_dir / "package.json").exists():
        raise HubError(f"{vikaki_dir} is not a vikaki checkout (no package.json)")
    port = urlsplit(config.http_origin).port
    command = [
        "pnpm",
        "serve",
        "--port",
        str(port),
        "--tts",
        tts,
        "--frame-ancestors",
        ",".join(frame_origins),
    ]
    if (vikaki_dir / PERSONAS).exists():
        command += ["--personas", str(vikaki_dir / PERSONAS)]
    try:
        # Its own session, so stopping it stops pnpm's child too (the hub itself).
        process = subprocess.Popen(command, cwd=vikaki_dir, start_new_session=True)  # noqa: S603
    except OSError as exc:
        raise HubError(f"cannot run pnpm: {exc.strerror}") from None
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise HubError("the vikaki hub stopped at start-up (is it built? run pnpm build)")
        with socket.socket() as probe:
            probe.settimeout(0.3)
            if probe.connect_ex(("127.0.0.1", port or 0)) == 0:
                return process
        time.sleep(0.3)
    stop_hub(process)
    raise HubError("the vikaki hub did not start within 90 seconds")


def stop_hub(process: subprocess.Popen[bytes]) -> None:
    """Stop the hub and what pnpm started for it."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
