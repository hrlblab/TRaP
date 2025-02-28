import numpy as np


def find_closest_in_A(A, B):
    """
    For each element in B, find the closest element in A.

    Parameters:
        A (np.ndarray): The array from which to find the closest values.
        B (np.ndarray): The array containing values to find the closest for.

    Returns:
        np.ndarray: An array containing the closest value from A for each element in B.
    """
    closest_values = []

    # Convert lists to NumPy arrays if they aren't already
    A = np.array(A)
    B = np.array(B)

    # Iterate over each element in B to find the closest element in A
    for b in B:
        idx = np.argmin(np.abs(A - b))
        closest_values.append(A[idx])

    return np.array(closest_values)