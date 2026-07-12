"""Evaluation API — runs the ground-truth harness and returns the scoreboard."""

from fastapi import APIRouter

from paaim.eval import run_eval

router = APIRouter()


@router.get("/run")
async def run() -> dict:
    """Execute the ground-truth eval and return the PASS/REVIEW scoreboard."""
    return await run_eval()
