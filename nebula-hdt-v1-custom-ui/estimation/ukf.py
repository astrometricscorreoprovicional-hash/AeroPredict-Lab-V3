import numpy as np

def _sigma_points(x, P, kappa):
    n = x.shape[0]
    S = np.linalg.cholesky((n + kappa) * P)
    sp = np.zeros((2*n + 1, n))
    sp[0] = x
    for i in range(n):
        sp[i+1]   = x + S[:, i]
        sp[i+1+n] = x - S[:, i]
    return sp

def _weights(n, kappa):
    Wm = np.full(2*n + 1, 1.0 / (2*(n + kappa)))
    Wc = np.full(2*n + 1, 1.0 / (2*(n + kappa)))
    Wm[0] = kappa / (n + kappa)
    Wc[0] = Wm[0]
    return Wm, Wc

def ukf_filter(z_series, dt_series, Q, R, x0, P0, kappa=1.0):
    """UKF for a simple constant-acceleration-in-altitude and constant-speed model.
    State x = [alt_km, speed_kms].
    Dynamics (discrete): 
        alt_{k+1} = alt_k + 0 * dt  + w1  (kept simple for demo)
        spd_{k+1} = spd_k           + w2
    Measurement: z = [alt_km, speed_kms] + v
    Q: process noise diag [q_alt, q_spd]
    R: measurement noise diag [r_alt, r_spd]
    Returns: arrays of x_est (N,2), P_diag (N,2), NEES (N,)
    """
    z_series = np.asarray(z_series)    # (N,2)
    dt_series = np.asarray(dt_series)  # (N,)
    n = 2
    N = z_series.shape[0]
    x = np.asarray(x0, dtype=float).reshape(n)
    P = np.diag(P0).astype(float)
    Qm = np.diag(Q).astype(float)
    Rm = np.diag(R).astype(float)

    xs = np.zeros((N, n))
    Ps = np.zeros((N, n))
    nees = np.zeros(N)

    for k in range(N):
        dt = float(dt_series[k])
        # UKF predict
        sp = _sigma_points(x, P, kappa)
        Wm, Wc = _weights(n, kappa)
        # propagate sigma points (very simple model)
        def f(xi):
            alt, spd = xi
            alt_n = alt  # no kinematics here (demo); can extend to integrate two-body mapped to alt
            spd_n = spd
            return np.array([alt_n, spd_n])
        X_pred = np.array([f(s) for s in sp])
        x_pred = np.sum(Wm[:,None] * X_pred, axis=0)
        P_pred = Qm.copy()
        for i in range(X_pred.shape[0]):
            d = (X_pred[i] - x_pred).reshape(n,1)
            P_pred += Wc[i] * (d @ d.T)

        # Update with measurement z_k
        def h(xi):
            return xi  # direct measurement of alt & speed

        Z_sig = np.array([h(s) for s in X_pred])
        z_pred = np.sum(Wm[:,None] * Z_sig, axis=0)
        S = Rm.copy()
        for i in range(Z_sig.shape[0]):
            dz = (Z_sig[i] - z_pred).reshape(n,1)
            S += Wc[i] * (dz @ dz.T)

        # Cross covariance
        Pxz = np.zeros((n, n))
        for i in range(Z_sig.shape[0]):
            dx = (X_pred[i] - x_pred).reshape(n,1)
            dz = (Z_sig[i] - z_pred).reshape(n,1)
            Pxz += Wc[i] * (dx @ dz.T)

        K = Pxz @ np.linalg.inv(S)
        z = z_series[k]
        x = x_pred + K @ (z - z_pred)
        P = P_pred - K @ S @ K.T

        xs[k] = x
        Ps[k] = np.diag(P)

        # NEES requires true error; caller may compute using truth if provided
        # Here we compute a proxy NEES using innovation: e_k^T S^{-1} e_k
        inn = (z - z_pred).reshape(n,1)
        nees[k] = float(inn.T @ np.linalg.inv(S) @ inn)

    return xs, Ps, nees
