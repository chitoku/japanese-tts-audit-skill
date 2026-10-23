"""Shared review timestamp validation."""
from datetime import datetime


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Invalid review timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Review timestamps must include a timezone')
    return parsed
