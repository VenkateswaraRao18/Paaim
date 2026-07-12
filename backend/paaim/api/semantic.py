"""
Semantic Disconnect API — cryptic machine code → human-readable action plan.

POST /api/semantic/diagnose
    {machine_id, code?} or {machine_id, signal_name?, plain_meaning?}
returns: decoded meaning + similar past fixes (Log Historian) + a step-by-step
SOP a junior operator can follow (SOP Dispatcher).
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.models import get_db
from paaim.semantic.plc_codes import lookup_code, list_codes
from paaim.semantic.maintenance_logs import get_historian
from paaim.semantic.sop_dispatcher import dispatch_sop
from paaim.semantic.vision_agent import inspect_image
from paaim.context.factory_context import get_context_service

router = APIRouter()


class DiagnoseRequest(BaseModel):
    machine_id: Optional[str] = None
    code: Optional[str] = None
    signal_name: Optional[str] = None
    plain_meaning: Optional[str] = None
    factory_id: str = "factory_001"


@router.get("/codes")
async def codes():
    """List the cryptic codes the operator can look up (demo helper)."""
    return {"codes": list_codes()}


@router.post("/diagnose")
async def diagnose(req: DiagnoseRequest, db: AsyncSession = Depends(get_db)):
    """Decode a cryptic alarm into a plain action plan."""
    # 1) Decode the code (Telemetry/Semantic interpretation)
    diagnosis = None
    if req.code:
        diagnosis = lookup_code(req.code)
        if not diagnosis:
            raise HTTPException(status_code=404,
                                detail=f"Unknown code '{req.code}'. Try one from GET /api/semantic/codes.")
    if not diagnosis:
        if not (req.machine_id and req.signal_name):
            raise HTTPException(status_code=400,
                                detail="Provide a `code`, or both `machine_id` and `signal_name`.")
        diagnosis = {
            "code": None, "machine_id": req.machine_id,
            "signal_name": req.signal_name,
            "plain_meaning": req.plain_meaning or f"{req.signal_name} reported on {req.machine_id}",
            "severity": "medium",
        }

    machine_id = diagnosis["machine_id"]
    signal_name = diagnosis["signal_name"]

    # 2) Log Historian — what fixed this before
    past_cases = get_historian().search(machine_id, signal_name, diagnosis.get("plain_meaning", ""))

    # 3) Operational context (reuses the Factory Context Layer)
    context = {}
    try:
        ctx = await get_context_service().build_context(req.factory_id, machine_id, db)
        context = ctx.to_dict()
    except Exception:
        pass

    # 4) SOP Dispatcher — the human-readable action plan
    sop = dispatch_sop(diagnosis, past_cases, context)

    return {
        "diagnosis": diagnosis,
        "past_cases": past_cases,
        "sop": sop,
        "context_available": bool(context),
    }


@router.post("/vision-inspect")
async def vision_inspect(
    file: UploadFile = File(...),
    machine_id: str = Form("unknown"),
    factory_id: str = Form("factory_001"),
    db: AsyncSession = Depends(get_db),
):
    """
    Vision Agent — upload a part photo, get a multimodal defect assessment
    (Gemini). The factory context is attached so the model knows what's being made.
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image.")

    context = {}
    try:
        ctx = await get_context_service().build_context(factory_id, machine_id, db)
        context = ctx.to_dict()
    except Exception:
        pass

    finding = inspect_image(image_bytes, file.content_type or "image/jpeg", machine_id, context)
    return {"machine_id": machine_id, "filename": file.filename, "vision": finding}
