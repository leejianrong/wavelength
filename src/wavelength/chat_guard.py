"""What an LLM seat may say in chat, and what it is told first (ADR-0005).

The framework's chat reply is built from the conversation alone, so it knows
nothing of the game. We prepend a context block, and that block is where a
leak could happen. It is therefore built from an explicit **allow-list** of
observation fields, never by copying the observation and removing the secret:
a field added to the observation later stays out of chat until someone adds it
here on purpose.

While the seat is the psychic it knows the target, so it does not chat at all
(no model call); the roles swap at the reveal, which reopens chat.
"""

from __future__ import annotations

from typing import Any

PSYCHIC_REFUSAL = (
    "I'm the psychic this round, so I can't talk about it until after the reveal. "
    "Ask me once you've guessed!"
)


def chat_context(obs: dict[str, Any]) -> str | None:
    """The game context to give a chatting seat, or ``None`` if it must stay
    silent (it is the psychic of an unfinished round)."""
    if obs.get("role") == "psychic":
        return None
    lines = ["[Game context from the referee, not said by your partner.]"]
    lines.append(
        "You and your partner are playing cooperative Wavelength: the psychic gives a clue for "
        "a hidden spot on a 0-100 dial between two opposites and the guesser guesses it. "
        "Points are shared."
    )
    if obs.get("phase") is None:
        lines.append(
            f"The match is over: {obs.get('total_score')} of {obs.get('target_score')} points."
        )
    else:
        spec = obs["spectrum"]
        lines.append(
            f"Round {obs.get('round')} of {obs.get('rounds')}. The dial runs from 0 "
            f"('{spec['left']}') to 100 ('{spec['right']}'). You are the guesser."
        )
        lines.append(
            f'Your partner\'s clue is "{obs["clue"]}".'
            if obs.get("clue")
            else "Your partner has not given a clue yet."
        )
        lines.append(f"Score so far: {obs.get('total_score')} of {obs.get('target_score')}.")
    for r in obs.get("history", []):
        spec = r["spectrum"]
        lines.append(
            f"Round {r['round']} (revealed): {spec['left']} to {spec['right']}, clue "
            f'"{r["clue"]}", guessed {r["guess"]}, target was {r["target"]}, {r["points"]} points.'
        )
    return "\n".join(lines)
