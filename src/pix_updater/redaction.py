from __future__ import annotations

import re
from collections.abc import Iterable

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)((?:password|token|secret|api[_-]?key)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(postgres(?:ql)?://[^:/\s]+:)[^@\s]+(@)"),
)


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        if pattern.groups == 2:
            result = pattern.sub(r"\1[REDACTED]\2", result)
        else:
            result = pattern.sub(r"\1[REDACTED]", result)
    return result
