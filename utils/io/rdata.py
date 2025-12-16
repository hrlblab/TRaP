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
    """
    Load spectrum data from file.

    Supports: .txt, .csv, .xlsx files
    Auto-detects delimiter for text files.

    Returns:
        np.ndarray: Column vector (N, 1) for consistency across the workflow
    """
    try:
        if filepath.endswith('.xlsx'):
            df = pd.read_excel(filepath, header=None)
        else:
            # Step 1: read first line
            with open(filepath, 'r', encoding='utf-8') as f:
                first_line = f.readline()

            # Step 2: detect delimiter
            if ',' in first_line:
                delimiter = ','
            elif '\t' in first_line:
                delimiter = '\t'
            else:
                delimiter = r'\s+'  # regex for whitespace

            # Step 3: read file accordingly
            if delimiter == r'\s+':
                df = pd.read_csv(filepath, sep=delimiter, header=None, engine='python')
            else:
                df = pd.read_csv(filepath, sep=delimiter, header=None)

        # Step 4: Format check
        if df.shape[0] == 1 and df.shape[1] > 1:
            return df.values.flatten().reshape(-1, 1).astype(np.float64)

        if df.shape[1] == 1:
            return df.iloc[:, 0].to_numpy().reshape(-1, 1).astype(np.float64)

        if df.shape[1] == 2:
            first_row = df.iloc[0, 0]
            if isinstance(first_row, str) and first_row.startswith("#"):
                df = pd.read_csv(filepath, sep=delimiter, header=None, skiprows=1)
            return df.iloc[:, 1].to_numpy().reshape(-1, 1).astype(np.float64)

        return df.iloc[:, 1:].mean(axis=1).to_numpy().reshape(-1, 1).astype(np.float64)

    except Exception as e:
        raise ValueError(f"Failed to read spectrum file: {e}")
