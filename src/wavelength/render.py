"""ASCII rendering of the viewer's observation, for the framework CLI.

The framework hands the renderer *the viewer's* observation (fw-ADR-0011), so
whatever it prints is already limited to what that seat may see. It must still
never add anything it did not get from the observation.
"""

from __future__ import annotations

from typing import Any

BAR_WIDTH = 41


def render_dial(left: str, right: str, guess: int | None = None, target: int | None = None) -> str:
    """One line: ``left [....G.....T....] right``. ``G`` guess, ``T`` target,
    ``X`` when they land on the same cell."""
    cells = ["."] * BAR_WIDTH

    def cell(value: int) -> int:
        return round(value / 100 * (BAR_WIDTH - 1))

    for mark, value in (("G", guess), ("T", target)):
        if value is None:
            continue
        i = cell(value)
        cells[i] = "X" if cells[i] not in (".", mark) else mark
    return f"{left} [{''.join(cells)}] {right}"


def _reveal_text(reveal: dict[str, Any]) -> str:
    spec = reveal["spectrum"]
    dial = render_dial(spec["left"], spec["right"], reveal["guess"], reveal["target"])
    return (
        f'Round {reveal["round"]} revealed: clue "{reveal["clue"]}"\n'
        f"{dial}\n"
        f"Guess {reveal['guess']}, target {reveal['target']}: "
        f"{reveal['points']} point{'s' if reveal['points'] != 1 else ''}"
    )


def render_observation(obs: dict[str, Any]) -> str:
    """Round header, then the latest reveal if the round just ended, then the
    current spectrum (with the target, if and only if the viewer is psychic)."""
    lines: list[str] = []
    history = obs.get("history", [])
    if history and obs.get("phase") in ("clue", None):
        lines.append(_reveal_text(history[-1]))
        lines.append("")
    if obs.get("phase") is None:
        verdict = "You won!" if obs.get("won") else "You did not reach the goal."
        lines.append(f"Match over: {obs['total_score']} / {obs['target_score']} points. {verdict}")
        return "\n".join(lines)
    spec = obs["spectrum"]
    lines.append(
        f"Round {obs['round']}/{obs['rounds']}  "
        f"score {obs['total_score']}/{obs['target_score']}  you: {obs['role']}"
    )
    lines.append(render_dial(spec["left"], spec["right"], target=obs.get("target")))
    if obs.get("target") is not None:
        lines.append(f"The target is {obs['target']} (0 = {spec['left']}, 100 = {spec['right']}).")
    if obs.get("clue"):
        lines.append(f'Clue: "{obs["clue"]}"')
    return "\n".join(lines)
