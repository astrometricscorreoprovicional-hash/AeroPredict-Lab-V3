import numpy as np

def nees(residuals_var_norm):
    return float(np.mean(residuals_var_norm))
