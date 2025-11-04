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

def ukf_filter_atm(z_series, dt_series, Q, R, x0, P0, kappa=1.0, g=9.80665):
    """UKF for atmospheric vertical channel.
    x = [alt_m, vd_mps];  z = [alt_m, vd_mps]
    Dynamics: alt_{k+1} = alt_k + vd_k * dt
              vd_{k+1}  = vd_k
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
        sp = _sigma_points(x, P, kappa)
        Wm, Wc = _weights(n, kappa)

        def f(xi):
            alt, vd = xi
            alt_n = alt + vd * dt
            vd_n = vd
            return np.array([alt_n, vd_n])

        X_pred = np.array([f(s) for s in sp])
        x_pred = np.sum(Wm[:,None] * X_pred, axis=0)
        P_pred = Qm.copy()
        for i in range(X_pred.shape[0]):
            d = (X_pred[i] - x_pred).reshape(n,1)
            P_pred += Wc[i] * (d @ d.T)

        def h(xi):  # direct measurement
            return xi

        Z_sig = np.array([h(s) for s in X_pred])
        z_pred = np.sum(Wm[:,None] * Z_sig, axis=0)
        S = Rm.copy()
        for i in range(Z_sig.shape[0]):
            dz = (Z_sig[i] - z_pred).reshape(n,1)
            S += Wc[i] * (dz @ dz.T)

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

        inn = (z - z_pred).reshape(n,1)
        nees[k] = float(inn.T @ np.linalg.inv(S) @ inn)

    return xs, Ps, nees
