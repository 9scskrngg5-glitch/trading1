"""Strates module — Trading analysis layers for ORACLE v2."""
from .base_strate import BaseStrate, StrateResult
from .polymarket_strate import PolymarketStrate, PolymarketOpportunity

__all__ = ["BaseStrate", "StrateResult", "PolymarketStrate", "PolymarketOpportunity"]
