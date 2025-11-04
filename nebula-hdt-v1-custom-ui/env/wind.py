import numpy as np

def dryden_like(t: float, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    return 5.0*np.sin(0.05*t) + rng.normal(0, 0.5)
