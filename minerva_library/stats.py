import numpy as np
from scipy.optimize import least_squares


def robust_least_squares(x, y, fun, c0 = np.zeros(3), loss='soft_l1', f_scale=0.1):

    def fit_fun(c, x, y):
        return fun(c, x) - y

    res_robust = least_squares(fit_fun, c0, loss=loss, f_scale=f_scale, args = (x, y))
    coeffs = res_robust.x
    
    return coeffs
