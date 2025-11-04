import numpy as np

def step_point_mass(state, u, dt, g=9.80665):
    """Modelo mínimo (punto-masa) para demo. state=[x,z,vx,vz] en 2D vertical.
    u: dict con 'ax','az' aceleraciones de control.
    """
    x,z,vx,vz = state
    ax = u.get('ax', 0.0)
    az = u.get('az', 0.0) - g
    x2 = x + vx*dt + 0.5*ax*dt*dt
    z2 = z + vz*dt + 0.5*az*dt*dt
    vx2 = vx + ax*dt
    vz2 = vz + az*dt
    return np.array([x2,z2,vx2,vz2])
