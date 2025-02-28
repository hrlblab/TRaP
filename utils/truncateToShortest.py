import numpy as np


def truncate_to_shortest(*args):
    """
    Truncate all input arrays to the length of the shortest array and combine into a matrix.

    Parameters:
    *args : variable number of 1D numpy arrays

    Returns:
    np.ndarray : 2D numpy array where each column represents one of the input arrays truncated to the length of the shortest array.
    """
    # Find the length of the shortest array
    min_length = min(len(arr) for arr in args)

    # Truncate each array to the shortest length and stack them horizontally
    output_array = np.column_stack([arr[:min_length] for arr in args])

    return output_array