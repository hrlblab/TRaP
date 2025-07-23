import numpy as np
from matplotlib import pyplot as plt
from scipy.linalg import pinv
from scipy.sparse import spdiags
from scipy.io import loadmat, savemat
from scipy.sparse import diags
from numpy.linalg import pinv


def savgol_filter(y, width, order, deriv):
    if y.ndim == 1:
        m = len(y)
        n = 1
    else:
        m, n = y.shape
    p = (width - 1) // 2

    # Create the Vandermonde matrix of powers
    x = np.vander(np.arange(-p, p + 1), N=order + 1, increasing=True)

    # Compute weights using pseudo-inverse
    weights = pinv(x)

    # Calculate coefficients for the desired derivative
    combined_matrix = np.ones((deriv, 1)) * np.arange(1, order + 2 - deriv) + np.arange(deriv).reshape(-1, 1) * np.ones(
        (1, order + 1 - deriv))
    coeff = np.prod(combined_matrix, axis=0)
    # coeff = np.prod([(np.arange(1, order + 2 - deriv) + i) for i in range(deriv)], axis=0)

    # Create sparse derivative matrix D for the bulk data
    diagonal_values = np.array([np.ones(n) * weights[deriv, i] * coeff[0] for i in range(weights.shape[1])])
    offsets = np.arange(p, -p - 1, -1)
    D = diags(diagonal_values, offsets, shape=(n, n)).toarray()

    # Handling the edges
    w1 = np.diag(coeff).dot(weights[deriv:order + 1])
    D[:width, :p + 1] = (x[:p + 1, :order - deriv + 1] @ w1).T
    D[n - width:n, n - p - 1:n] = (x[p:width, :order - deriv + 1] @ w1).T

    # Filter the input data
    y_hat = y.dot(D)

    return y_hat, D

# Example usage
# data = loadmat('test_data.mat')  # Assuming 'y' is stored under 'y' key
# y = data['y']
# if y.ndim == 1:
#     y = y[np.newaxis, :]  # Ensure y is a 2D array
#
# # Apply Savitzky-Golay filter
# y_hat, D = savgol_filter(y, 15, 2, 0)
#
# # Plot the results
# plt.figure(figsize=(10, 5))
# plt.plot(y.flatten(), 'b-', label='Original Data')
# plt.plot(y_hat.flatten(), 'r-', label='Filtered Data', linewidth=2)
# plt.legend()
# plt.xlabel('Index')
# plt.ylabel('Value')
# plt.title('Savitzky-Golay Filter Application')
# plt.grid(True)
# plt.show()
