"""Spectrum deck: a validated list of ``(left, right)`` label pairs.

The bundled deck is original content (PLAN §Scope); ``--config deck=<file>``
swaps in another file of the same shape. ``format`` is the file's own schema
version, separate from the engine's ``schema_version`` (QUESTIONS Q20).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

DECK_FORMAT = 1


@dataclass(frozen=True)
class Spectrum:
    """Two opposite labels. A dial value of 0 is ``left`` and 100 is ``right``."""

    left: str
    right: str

    def to_dict(self) -> dict[str, str]:
        return {"left": self.left, "right": self.right}


def parse_deck(data: Any) -> list[Spectrum]:
    """Validate decoded deck JSON. Raises ``ValueError`` with a specific reason."""
    if not isinstance(data, dict) or data.get("format") != DECK_FORMAT:
        raise ValueError(f"deck must be an object with format {DECK_FORMAT}")
    raw = data.get("spectra")
    if not isinstance(raw, list) or not raw:
        raise ValueError("deck must have a non-empty 'spectra' list")
    spectra: list[Spectrum] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"spectra[{index}] must be an object")
        left, right = item.get("left"), item.get("right")
        if not isinstance(left, str) or not isinstance(right, str):
            raise ValueError(f"spectra[{index}] needs 'left' and 'right' text labels")
        if not left.strip() or not right.strip():
            raise ValueError(f"spectra[{index}] needs non-empty 'left' and 'right' labels")
        key = (left.strip().lower(), right.strip().lower())
        if key in seen or (key[1], key[0]) in seen:
            raise ValueError(f"spectra[{index}] duplicates an earlier spectrum: {left!r}/{right!r}")
        seen.add(key)
        spectra.append(Spectrum(left.strip(), right.strip()))
    return spectra


def load_deck(path: str | Path | None = None) -> list[Spectrum]:
    """The bundled deck when ``path`` is ``None``, else the file at ``path``."""
    if path is None:
        text = resources.files("wavelength").joinpath("data/spectra.json").read_text("utf-8")
    else:
        try:
            text = Path(path).read_text("utf-8")
        except OSError as exc:
            raise ValueError(f"cannot read deck {str(path)!r}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"deck is not valid JSON: {exc}") from exc
    return parse_deck(data)
