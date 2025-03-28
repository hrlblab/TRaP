import os

import numpy as np
import pandas as pd
from scipy.io import loadmat

def read_txt_file(filepath, delimiter=',', header=None):
    try:
        data = pd.read_csv(filepath, delimiter=delimiter, header=header, dtype=np.float64)
        return data
    except Exception as e:
        print(f"Read File Err：{e}")
        return None

def getspectrumfrompath(path):
    _, file_extension = os.path.splitext(path)

    if file_extension.lower() == '.csv':
        data = pd.read_csv(path, delimiter='\t', header=None).T.astype(float).to_numpy()[0]
    elif file_extension.lower() in ['.xls', '.xlsx']:
        data = pd.read_excel(path, header=None).T.astype(float).to_numpy()
    else:
        raise ValueError("Unsupported file type: " + file_extension)

    spectrum = data.iloc[:, 1:].mean(axis=1)
    return spectrum


def getwlcorrfrompath(path):
    _, file_extension = os.path.splitext(path)

    if file_extension.lower() == '.csv':
        wl_corr = pd.read_csv(path, delimiter='\t', header=None)
    elif file_extension.lower() in ['.xls', '.xlsx']:
        wl_corr = pd.read_excel(path, header=None)
    else:
        raise ValueError("Unsupported file type: " + file_extension)

    return wl_corr


def getwvnfrompath(path):
    wvn_data = loadmat(path)
    wvn = wvn_data['Cal']['Wvn'][0, 0]
    # print(wvn)
    return np.array(wvn, dtype=np.float64)

def load_spectrum_data(filepath):
    try:
        # Try reading with header=None first
        df = pd.read_csv(filepath, header=None)
    except Exception:
        # Retry with default header if header=None fails
        df = pd.read_csv(filepath)

    # Handle 1D case: single line
    if df.shape[0] == 1:  # one row, many columns → make it a column vector

        data = df.values.flatten().reshape(-1, 1).astype(np.float64)
        return data

    # Handle single column file
    if df.shape[1] == 1:  # one column
        data = df.iloc[:, 0].to_numpy().reshape(-1, 1).astype(np.float64)
        return data

    # Handle two columns with header
    if df.shape[1] == 2 and not np.issubdtype(df.iloc[0, 1], np.number):
        # Try re-reading and skipping header row
        df = pd.read_csv(filepath, skiprows=1, header=None)
        if df.shape[1] == 2:
            data = df.iloc[:, 1].to_numpy().reshape(-1, 1).astype(np.float64)
            return data

    # Handle multi-column: average from second column
    if df.shape[1] > 1:
        data = df.iloc[:, 1:].mean(axis=1).to_numpy().reshape(-1, 1).astype(np.float64)
        return data
