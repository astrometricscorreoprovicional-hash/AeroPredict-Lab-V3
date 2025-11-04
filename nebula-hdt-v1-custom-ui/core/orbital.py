import numpy as np

MU_EARTH = 3.986004418e14
J2 = 1.08262668e-3
R_E = 6378137.0

def twobody_step(r, v, dt, mu=MU_EARTH):
    a = -mu * r / np.linalg.norm(r)**3
    v2 = v + a*dt
    r2 = r + v2*dt
    return r2, v2
