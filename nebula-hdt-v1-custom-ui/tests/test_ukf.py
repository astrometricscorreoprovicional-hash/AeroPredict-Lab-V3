import numpy as np
from estimation.ukf import ukf_filter

def test_ukf_shapes_and_stability():
    # Synthetic truth
    N = 200
    t = np.linspace(0, 199, N)
    alt = 400.0 + 0.1*np.sin(2*np.pi*t/200)     # km
    spd = 7.67 + 0.01*np.cos(2*np.pi*t/200)     # km/s

    rng = np.random.default_rng(42)
    z_alt = alt + rng.normal(0, 0.01, size=N)   # 10 m noise
    z_spd = spd + rng.normal(0, 0.001, size=N)  # 1 m/s noise

    z = np.vstack([z_alt, z_spd]).T
    dt = np.diff(t, prepend=t[0])

    xs, Ps, nees = ukf_filter(
        z_series=z,
        dt_series=dt,
        Q=[1e-4, 1e-5],
        R=[1e-4, 1e-6],
        x0=[z_alt[0], z_spd[0]],
        P0=[1.0, 0.1],
    )

    # Shapes
    assert xs.shape == (N, 2)
    assert Ps.shape == (N, 2)
    assert nees.shape == (N,)

    # Stability: variances should remain finite and positive
    assert np.all(Ps > 0)
    assert np.isfinite(Ps).all()
    assert np.isfinite(xs).all()

    # Basic sanity: NEES shouldn't explode
    assert float(np.nanmax(nees)) < 50.0
