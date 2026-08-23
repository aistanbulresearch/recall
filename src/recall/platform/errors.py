from __future__ import annotations


class PlatformError(RuntimeError):
    """Typed platform failure raised instead of returning an optimistic result.

    Every unreachable or unverified managed dependency must surface as this
    error or as a typed degraded receipt. No caller may infer success from a
    missing signal.
    """

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        message = code if detail is None else f"{code}:{detail}"
        super().__init__(message)
