import numpy as np
from numpy.polynomial.polynomial import Polynomial


def lsqpolyval(P, xx):
    xx = np.asarray(xx)
    if xx.ndim > 1 and xx.shape[0] < xx.shape[1]:
        xx = xx.T  # Ensure xx is a column vector if not already

    mx = P['Scale'][0]
    sx = P['Scale'][1]
    p = P['Coefficients']
    order = p.shape[0] - 1

    xx = (xx - mx) / sx
    # Corner Case
    if isinstance(xx, (int, float)):
        length = 1
    else:
        length = len(xx)
    yy = np.zeros((length, p.shape[1]))
    erryy = np.zeros_like(yy)

    for k in range(p.shape[1]):
        input_co = p[::-1, k]

        yy[:, k] = np.polyval(p[:, k], xx)  # Note: polyval expects coefs from highest to lowest degree

        A = np.zeros((order + 1, length))
        for i in range(order + 1):
            A[i, :] = xx ** 2 * i  # Assuming zero-based index matches (i-1) in MATLAB

        A = A[::-1]
        # Assuming P['Covariance'] is a 2D matrix where each column k corresponds to variances for the k-th polynomial
        variances = np.diag(P['Covariance']) ** 2
        erryy[:, k] = np.sqrt(np.sum(A * variances[:, np.newaxis], axis=0))

    return yy.T, erryy.T


# Example usage
# P = {
#     'Scale': [0, 1],  # mean and standard deviation for scaling
#     'Coefficients': np.array([[1], [-1], [2], [-2], [3], [-3]]),  # coefficients for a 5th degree polynomial
#     'Covariance': np.diag([0.1, 0.05, 0.15, 0.1, 0.05, 0.1])  # more complex covariance matrix
# }
#
# # Define more x values for evaluation
# xx = np.linspace(-2, 2, 10)  # 10 points from -2 to 2
#
# yy, erryy = lsqpolyval(P, xx)
# print("Evaluated Polynomial Values:\n", yy)
# print("Error Estimates:\n", erryy)