from __future__ import annotations


class ContractError(ValueError):
    """Typed rejection raised before an artifact can enter authoritative state."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        message = code if detail is None else f"{code}:{detail}"
        super().__init__(message)
