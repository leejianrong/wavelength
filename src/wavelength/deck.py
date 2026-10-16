"""Spectrum deck: a validated list of spectra, each two opposite labels and six zone names.

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

DECK_FORMAT = 2
SUPPORTED_FORMATS = (1, 2)  # 1 has no zone names; they are generated (ADR-0007)
REGION_COUNT = 6
MAX_REGION_CHARS = 28


def region_index(value: int) -> int:
    """Which of the six equal zones a dial value is in: 0 is the left extreme, 5 the right."""
    return min(REGION_COUNT - 1, max(0, value) * REGION_COUNT // 100)


def generated_regions(left: str, right: str) -> tuple[str, ...]:
    """Zone names for a spectrum that has none written (a format 1 deck)."""
    return (
        f"Far toward {left}",
        f"Toward {left}",
        f"A little toward {left}",
        f"A little toward {right}",
        f"Toward {right}",
        f"Far toward {right}",
    )


@dataclass(frozen=True)
class Spectrum:
    """Two opposite labels and six zone names between them. A dial value of 0 is ``left`` and
    100 is ``right``; ``regions`` run left to right (ADR-0007). With no ``regions`` given they
    are generated, so a spectrum always has six."""

    left: str
    right: str
    regions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        regions = tuple(self.regions) or generated_regions(self.left, self.right)
        object.__setattr__(self, "regions", regions)

    def region(self, value: int) -> str:
        """The zone name for a dial value."""
        return self.regions[region_index(value)]

    def to_dict(self) -> dict[str, Any]:
        return {"left": self.left, "right": self.right, "regions": list(self.regions)}


def _parse_regions(raw: Any, index: int) -> tuple[str, ...]:
    where = f"spectra[{index}] 'regions'"
    if not isinstance(raw, list) or len(raw) != REGION_COUNT:
        raise ValueError(f"{where} must be a list of exactly {REGION_COUNT} zone names")
    names: list[str] = []
    for name in raw:
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{where} must hold non-empty text")
        if len(name.strip()) > MAX_REGION_CHARS:
            raise ValueError(f"{where}: {name!r} is longer than {MAX_REGION_CHARS} characters")
        names.append(name.strip())
    if len({n.lower() for n in names}) != REGION_COUNT:
        raise ValueError(f"{where} must be {REGION_COUNT} different names: {names}")
    return tuple(names)


def parse_deck(data: Any) -> list[Spectrum]:
    """Validate decoded deck JSON. Raises ``ValueError`` with a specific reason."""
    if not isinstance(data, dict) or data.get("format") not in SUPPORTED_FORMATS:
        raise ValueError(
            f"deck must be an object with format {' or '.join(map(str, SUPPORTED_FORMATS))}"
        )
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
        regions = _parse_regions(item["regions"], index) if "regions" in item else ()
        spectra.append(Spectrum(left.strip(), right.strip(), regions))
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
