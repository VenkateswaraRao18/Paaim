"""Data-source connectivity: reach a source, prove it, and sample it.

Separate from `paaim.normalization`, which only translates a payload once it has
arrived. This is the layer that decides whether PAAIM can talk to a plant at all.
"""

from paaim.sources.connectors import (
    SOURCE_TYPES,
    ConnectionResult,
    DiscoveryResult,
    discover,
    test_connection,
)

__all__ = [
    "SOURCE_TYPES",
    "ConnectionResult",
    "DiscoveryResult",
    "discover",
    "test_connection",
]
