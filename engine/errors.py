"""Engine exception hierarchy."""

from __future__ import annotations


class PricingError(Exception):
    """Base class for all engine errors."""


class UnsupportedCombinationError(PricingError):
    """The chosen method cannot price this (instrument, model) pair."""


class MarketDataError(PricingError):
    """Market data is missing, inconsistent or outside its domain."""
