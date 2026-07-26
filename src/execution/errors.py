"""Module 14 fail-closed errors."""


class ExecutionValidationError(ValueError):
    """An execution boundary validation failed."""


class InvalidTransitionError(ExecutionValidationError):
    """An execution state transition was not permitted."""
