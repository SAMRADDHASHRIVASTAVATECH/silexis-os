"""Shared utility functions."""


def clean_text(text: str) -> str:
    return text.strip().lower()


def truncate(text: str, max_len: int = 512) -> str:
    return text[:max_len] if len(text) > max_len else text
