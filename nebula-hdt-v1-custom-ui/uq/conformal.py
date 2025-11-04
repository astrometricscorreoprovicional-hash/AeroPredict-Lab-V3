import numpy as np

def conformal_interval(y_pred, calib_residuals, alpha=0.1):
    q = np.quantile(np.abs(calib_residuals), 1-alpha)
    return float(q)
