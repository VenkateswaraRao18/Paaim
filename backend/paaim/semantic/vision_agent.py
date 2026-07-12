"""
Vision Agent — multimodal defect inspection via Gemini.

Takes a photo of a manufactured part and the machine context, and returns a
structured defect assessment. Uses Gemini's NATIVE multimodal capability (image
+ text in one call) — no separate computer-vision model to train, so it stays
the same shape as the other LLM agents.

In production this image comes from a line camera (e.g. the Future Factories
multimodal dataset); here an operator can upload any part photo.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_PROMPT = """You are a manufacturing QUALITY INSPECTOR examining a photo of a part or machine.
Identify any visible defect (e.g. crack, scratch, dent, deformation, discoloration,
solder bridge, missing component, contamination, surface finish problem).

Context: machine = {machine_id}{ctx}

Respond with ONLY valid JSON:
{{
  "defect_found": <true|false>,
  "defect_type": "<short label, or 'none'>",
  "severity": "<none|minor|major|critical>",
  "description": "<one plain sentence an operator understands>",
  "confidence": <float 0.0-1.0>,
  "recommended_disposition": "<accept | rework | scrap | hold_for_review>"
}}
No markdown, only the JSON."""


def inspect_image(image_bytes: bytes, mime_type: str, machine_id: str = "unknown",
                  context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a multimodal defect inspection on an image."""
    ctx_txt = ""
    if context and context.get("active_work_order"):
        wo = context["active_work_order"]
        ctx_txt = f", currently producing {wo.get('product_name', wo.get('work_order_id',''))}"

    try:
        from PIL import Image
        from paaim.agents.base import _get_gemini
        client, available = _get_gemini()
        if not (available and client):
            return {"defect_found": None, "error": "Vision requires Gemini (not configured)",
                    "_source": "unavailable"}

        img = Image.open(io.BytesIO(image_bytes))
        prompt = _PROMPT.format(machine_id=machine_id, ctx=ctx_txt)
        resp = client.generate_content([prompt, img])
        text = (resp.text or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1].replace("json", "", 1).strip()
        result = json.loads(text)
        result["_source"] = "gemini_multimodal"
        return result
    except Exception as e:
        logger.warning(f"Vision inspection failed: {e}")
        return {"defect_found": None, "error": str(e), "_source": "error"}
