"""
Defense module for LLM security.
Implements P2P (Poison-to-Poison) defense and other security mechanisms.

"""

from .p2p_defense import P2PDefense, P2PConfig, BenignTrigger
from .trigger_generator import TriggerGenerator
from .safety_validator import SafetyValidator

__all__ = [
    "P2PDefense",
    "P2PConfig",
    "BenignTrigger",
    "TriggerGenerator",
    "SafetyValidator"
]
