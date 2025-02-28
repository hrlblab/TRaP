import numpy as np
from scipy.linalg import cholesky, solve
from scipy.special import gammainc


def lsqpolyfit(x, y, sy, order):
    x = np.asarray(x).flatten()
    y = np.asarray(y).flatten()

    if sy is None:
        sy = np.ones_like(y)
    else:
        sy = np.asarray(sy).flatten()
        sy[sy == 0] = 0.01  # Replace zeros in sy with a small value

    # Normalize 'x' using sample standard deviation (ddof=1)
    mx = np.mean(x)
    sx = np.std(x, ddof=1)
    x_scaled = (x - mx) / sx

    # Construct Vandermonde matrix explicitly
    A = np.vstack([(x_scaled ** i) / sy for i in range(order, -1, -1)])

    # Construct weighted y-values
    b = y / sy
    # Solve least squares problem using Cholesky decomposition
    ATA = A @ A.T
    ATb = A @ b.T
    C = cholesky(ATA)
    # p = solve(C, solve(C.T, ATb))
    Ab_transposed = np.dot(A, b.reshape(-1, 1))
    temp = np.linalg.solve(C.T, Ab_transposed)
    p = np.linalg.solve(C, temp)
    # Compute covariance matrix
    covariance = np.linalg.inv(C.T @ C)

    # Calculate chi-squared value
    residuals = (y - np.polyval(p[:], x_scaled)) / sy
    chisqr = np.sum(residuals ** 2)

    # Compute probability using gammainc
    dof = len(x) - order
    probability = gammainc(dof / 2, chisqr / 2)

    # Store results in a dictionary
    P = {
        "Covariance": covariance,
        "Probability": probability,
        "Coefficients": p,
        "Scale": [mx, sx]
    }

    return P
#
# # 示例数据
# x = np.array([1, 2, 3, 4, 5])
# y = np.array([1.2, 1.9, 3.0, 4.1, 5.1])
# sy = np.array([0.1, 0.1, 0.2, 0.2, 0.3])
#
# # 调用函数
# P = lsqpolyfit(x, y, sy, order=2)
#
# # 打印结果
# print("Coefficients:", P["Coefficients"])
# print("Covariance matrix:", P["Covariance"])
# print("Probability:", P["Probability"])
# print("Scale factors (mean, std):", P["Scale"])