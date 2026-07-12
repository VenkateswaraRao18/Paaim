"""
Stream Bridge — connects live sensor streams to the decision pipeline.

A StreamAgent subscribes to one signal on the factory-stream feed (over SSE),
watches it live, and when a reading breaches its rule it raises an event onto
the Event Bus. The existing bus consumer then runs the full pipeline and a
governed decision appears on the dashboard.

This is what makes an agent feel "connected and real": it pulls live data from
an external streaming API and acts on it.
"""

from paaim.stream_bridge.bridge import get_stream_bridge, StreamBridge
from paaim.stream_bridge.agent import StreamAgent

__all__ = ["get_stream_bridge", "StreamBridge", "StreamAgent"]
