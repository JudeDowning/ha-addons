from datetime import datetime
from backend.core.normalisation import build_fingerprint

def test_build_fingerprint_deterministic():
    dt = datetime(2025, 1, 1, 12, 0)
    fp1 = build_fingerprint("Eli", "meal", dt, "Lunch – ate 75%")
    fp2 = build_fingerprint("eli", "MEAL", dt, "Lunch – ate 75%")
    assert fp1 == fp2
