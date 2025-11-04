from typing import List, Dict

def cusum(residuals: List[float], k: float = 0.5, h: float = 5.0) -> bool:
    s_pos = 0.0
    for r in residuals:
        s_pos = max(0.0, s_pos + r - k)
        if s_pos > h:
            return True
    return False

def root_cause_stub() -> str:
    return "engine_out"
