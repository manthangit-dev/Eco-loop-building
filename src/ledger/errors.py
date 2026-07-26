"""Stable Comfort Ledger policy failures."""


class LedgerValidationError(ValueError):
    """Fail-closed error with a stable reason code."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)
