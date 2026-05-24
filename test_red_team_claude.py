#!/usr/bin/env python3
"""Test Claude API integration for Red-Team Agent."""

import asyncio
import os
from paaim.governance.red_team import RedTeamAgent, CLAUDE_AVAILABLE
from paaim.models import RiskLevel


async def test_red_team_claude():
    """Test red-team with Claude API."""
    print("\n" + "=" * 70)
    print("PAAIM Red-Team Agent: Claude API Integration Test")
    print("=" * 70)

    # Check if Claude API is available
    api_key = os.getenv("ANTHROPIC_API_KEY")
    print(f"\n1. Environment Check")
    print(f"   Claude SDK Available: {CLAUDE_AVAILABLE}")
    print(f"   API Key Configured: {'✓' if api_key else '✗'}")

    # Initialize red-team agent
    red_team = RedTeamAgent(use_claude=CLAUDE_AVAILABLE and bool(api_key))
    print(f"   Red-Team Mode: {'Claude API' if red_team.use_claude else 'Hardcoded Rules (Fallback)'}")

    # Test case 1: Critical safety action
    print(f"\n2. Test Case 1: Zone Intrusion (Critical Safety)")
    print("-" * 70)

    review_1 = red_team.challenge(
        action_name="stop_line",
        confidence=0.95,
        evidence_signals=["zone_intrusion_detected", "worker_alert"],
        event_context={
            "zone_id": "restricted_zone_a",
            "worker_id": "W123",
            "breach_duration_ms": 500,
            "sensor_confidence": 0.98,
        },
        risk_level=RiskLevel.CRITICAL,
    )

    print(f"   Action: stop_line")
    print(f"   Risk Factors:")
    for factor in review_1.risk_factors[:3]:
        print(f"     - {factor}")
    print(f"   Overall Assessment: {review_1.overall_risk_assessment}")
    print(f"   Confidence Adjustment: {review_1.confidence_adjustment:+.2f}")

    # Test case 2: Medium-risk action
    print(f"\n3. Test Case 2: Schedule Maintenance (Medium Risk)")
    print("-" * 70)

    review_2 = red_team.challenge(
        action_name="schedule_maintenance",
        confidence=0.82,
        evidence_signals=["vibration_anomaly", "temperature_rising"],
        event_context={
            "machine_id": "pump_motor_05",
            "baseline_vibration": 2.3,
            "current_vibration": 7.5,
            "frequency_hz": 2400,
        },
        risk_level=RiskLevel.MEDIUM,
    )

    print(f"   Action: schedule_maintenance")
    print(f"   Risk Factors:")
    for factor in review_2.risk_factors[:3]:
        print(f"     - {factor}")
    print(f"   Suggested Alternatives:")
    for alt in review_2.suggested_alternatives[:2]:
        print(f"     • {alt}")
    print(f"   Overall Assessment: {review_2.overall_risk_assessment}")

    # Test case 3: Low-risk action
    print(f"\n4. Test Case 3: Shift Load (Low Risk)")
    print("-" * 70)

    review_3 = red_team.challenge(
        action_name="shift_non_critical_load",
        confidence=0.78,
        evidence_signals=["peak_pricing_detected", "flexible_load_available"],
        event_context={
            "pricing_tier": "peak",
            "pricing_per_kwh": 0.45,
            "normal_pricing": 0.12,
            "estimated_savings": 3500,
        },
        risk_level=RiskLevel.LOW,
    )

    print(f"   Action: shift_non_critical_load")
    print(f"   Risk Factors: {len(review_3.risk_factors)} identified")
    print(f"   Assumptions Challenged: {len(review_3.assumptions_challenged)}")
    print(f"   Overall Assessment: {review_3.overall_risk_assessment}")

    # Summary
    print(f"\n5. Summary")
    print("-" * 70)
    print(f"   ✓ Red-Team agent initialized successfully")
    print(f"   ✓ All 3 test cases completed without errors")
    print(f"   ✓ Reviews generated with {['hardcoded rules', 'Claude API'][int(red_team.use_claude)]}")

    if red_team.use_claude:
        print(f"\n   Mode: Production (Claude API enabled)")
        print(f"   All decisions have intelligent context-aware risk assessment")
    else:
        print(f"\n   Mode: Demo/Fallback (Hardcoded Rules)")
        print(f"   Set ANTHROPIC_API_KEY to enable Claude API integration")

    print("\n" + "=" * 70)
    print("Test Complete ✓")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(test_red_team_claude())
