import numpy as np

class EKF:
    def __init__(self, Q: float = 1e-2, R: float = 1e-1):
        self.Q = Q; self.R = R
    def step(self, x, P, z, H=1.0):
        # demo scalar
        # predict
        x_pred = x
        P_pred = P + self.Q
        # update
        y = z - H*x_pred
        S = H*P_pred*H + self.R
        K = P_pred*H/S
        x = x_pred + K*y
        P = (1-K*H)*P_pred
        return x, P, y, S
