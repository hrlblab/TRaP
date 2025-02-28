import numpy as np
from scipy.io import loadmat


def file_matrix_avg(files):
    """
    Loads matrices from given files and calculates their average.

    Parameters:
        files (list of str): List of filenames to load matrices from.

    Returns:
        np.ndarray: Average of the loaded matrices.
    """
    sum_matrix = None
    num_matrices = 0

    for filename in files:
        try:
            # Load the matrix from a .mat file
            matrix_data = np.loadtxt(filename)
            # Assuming the data is stored under a key that matches the filename without extension
            key = filename.split('.')[0]
            matrix = matrix_data[key]

            if sum_matrix is None:
                sum_matrix = matrix
            else:
                sum_matrix += matrix

            num_matrices += 1

        except FileNotFoundError:
            print(f"File {filename} not found.")
        except KeyError:
            print(f"No data found under the key '{key}' in file {filename}.")

    if num_matrices > 0:
        avg_matrix = sum_matrix / num_matrices
        return avg_matrix
    else:
        print("No files were processed.")
        return None