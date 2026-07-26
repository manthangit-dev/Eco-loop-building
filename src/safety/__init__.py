"""Independent Module 8 fail-closed actuation gate."""

from src.safety.guard import SafetyGuard
from src.safety.models import GuardDecision, GuardedCommand, ProposedCommand

__all__ = ["GuardDecision", "GuardedCommand", "ProposedCommand", "SafetyGuard"]
