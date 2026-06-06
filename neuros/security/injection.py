"""Prompt injection detector — pattern-based, zero external dependencies."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PATTERNS: dict[str, tuple[float, list[re.Pattern]]] = {
    "role_confusion": (
        0.4,
        [
            re.compile(p, re.IGNORECASE)
            for p in [
                r"ignore (previous|all|prior|above)",
                r"disregard (your|all) instructions",
                r"you are now",
                r"new persona",
                r"act as (if you are|a|an)",
                r"forget (that you|your)",
            ]
        ],
    ),
    "command_override": (
        0.5,
        [
            re.compile(p, re.IGNORECASE)
            for p in [
                r"system prompt",
                r"override (your|the) (instructions|rules)",
                r"developer mode",
                r"jailbreak",
                r"do anything now",
                r"DAN mode",
            ]
        ],
    ),
    "prompt_leakage": (
        0.3,
        [
            re.compile(p, re.IGNORECASE)
            for p in [
                r"repeat (your|the) (system|initial) (prompt|instructions)",
                r"what (are|were) your instructions",
                r"show me your prompt",
            ]
        ],
    ),
    "context_poisoning": (
        0.2,
        [
            re.compile(p, re.IGNORECASE)
            for p in [
                r"previous conversation",
                r"you said earlier",
                r"as we discussed",
                r"you already agreed",
                r"you confirmed",
            ]
        ],
    ),
    "tool_hijacking": (
        0.4,
        [
            re.compile(p, re.IGNORECASE)
            for p in [
                r"call (the|a) (tool|function|skill)",
                r"execute (bash|shell|python|code)",
                r"run (this|the following) (command|script)",
            ]
        ],
    ),
    "obfuscation": (
        0.3,
        [
            re.compile(p)
            for p in [
                r"[A-Za-z0-9+/]{20,}={0,2}",
                r"\\u[0-9a-fA-F]{4}",
                r"0x[0-9a-fA-F]{6,}",
            ]
        ],
    ),
}


@dataclass
class InjectionResult:
    score: float
    triggered: list[str] = field(default_factory=list)
    blocked: bool = False


def check(text: str, threshold: float = 0.6) -> InjectionResult:
    """Check text for prompt injection patterns. Returns InjectionResult."""
    triggered: list[str] = []
    total_score = 0.0

    for category, (weight, patterns) in _PATTERNS.items():
        for pattern in patterns:
            if pattern.search(text):
                triggered.append(category)
                total_score += weight
                break  # one match per category is enough

    score = min(total_score, 1.0)
    return InjectionResult(score=score, triggered=triggered, blocked=score >= threshold)
