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


def port_is_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def start_hub(
    vikaki_dir: Path, config: VoiceConfig, *, tts: str, frame_origins: list[str]
) -> subprocess.Popen[bytes] | None:
    """Run ``pnpm serve`` in a vikaki checkout (built, with ``make install-voice`` for ``kokoro``)
    and wait for its port. ``tts`` is ``fake`` or ``kokoro``. Returns ``None`` when something is
    already listening on the port (probably a hub you started): that one is used as it is, and its
    voice and framing settings are not ours to change."""
    if not (vikaki_dir / "package.json").exists():
        raise HubError(f"{vikaki_dir} is not a vikaki checkout (no package.json)")
    port = urlsplit(config.http_origin).port
    if port is not None and port_is_open(port):
        return None
    args = [
        "--port",
        str(port),
        "--tts",
        tts,
        "--frame-ancestors",
        ",".join(frame_origins),
    ]
    # `pnpm serve` runs this same tsx command, but pnpm prints an error banner whenever it is
    # stopped by a signal, so run tsx itself when the checkout has it.
    cli = vikaki_dir / "packages" / "cli"
    tsx = cli / "node_modules" / ".bin" / "tsx"
    if tsx.exists():
        command, cwd = [str(tsx), "src/index.ts", "serve", *args], cli
    else:
        command, cwd = ["pnpm", "--silent", "serve", *args], vikaki_dir
    if (vikaki_dir / PERSONAS).exists():
        command += ["--personas", str(vikaki_dir / PERSONAS)]
    try:
        # Its own session, so stopping it stops pnpm's child too (the hub itself).
        process = subprocess.Popen(command, cwd=cwd, start_new_session=True)  # noqa: S603
    except OSError as exc:
        raise HubError(f"cannot start the hub: {exc.strerror}") from None
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise HubError("the vikaki hub stopped at start-up (is it built? run pnpm build)")
        if port_is_open(port or 0):
            return process
        time.sleep(0.3)
    stop_hub(process)
    raise HubError("the vikaki hub did not start within 90 seconds")


def stop_hub(process: subprocess.Popen[bytes], grace: float = 8.0) -> None:
    """Stop the hub and what pnpm started for it, as Ctrl+C would: SIGINT lets it say
    "Stopping... Stopped." and exit cleanly; SIGKILL only if it does not within ``grace``."""
    for sig, wait in ((signal.SIGINT, grace), (signal.SIGKILL, 2.0)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue
