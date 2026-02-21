import os
from io import StringIO

import numpy as np
import pandas as pd
from scipy.io import loadmat


def _skip_header_lines(filepath):
    """
    Read a text file and return (data_lines, skipped_count).
    Skips leading lines whose first token is not a number.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        raw_lines = f.readlines()

    lines = [l for l in raw_lines if l.strip()]
    skipped = 0
    for line in lines:
        token = line.strip().split(',')[0].split('\t')[0].split()[0]
        try:
            # Try replacing comma decimal too
            float(token.replace(',', '.', 1) if '.' not in token else token)
            break
        except ValueError:
            skipped += 1
    return lines[skipped:], skipped


def _detect_european_decimal(sample_line):
    """
    Detect if a line uses European decimal format (comma as decimal separator).
    e.g. "1,1214" means 1.1214

    Returns True if European decimal is detected.
    """
    s = sample_line.strip()
    if '\t' in s or ';' in s:
        return False
    parts = s.split(',')
    if len(parts) == 2:
        left, right = parts[0].strip(), parts[1].strip()
        if '.' not in left and '.' not in right:
            try:
                float(left)
                float(right)
                return True
            except ValueError:
                pass
    return False


def _read_text_to_df(filepath):
    """
    Robustly read a numeric text file into a DataFrame.

    Handles:
      - Header rows (non-numeric first lines are skipped)
      - European decimal format: "1,1214" means 1.1214
      - Semicolon-delimited files with comma decimals
      - Tab / space / comma delimiters
    """
    data_lines, skip_count = _skip_header_lines(filepath)
    if not data_lines:
        raise ValueError(f"No numeric data found in: {filepath}")

    sample = data_lines[0].strip()

    # Check European decimal format
    if _detect_european_decimal(sample):
        text = '\n'.join(l.replace(',', '.') for l in data_lines)
        df = pd.read_csv(StringIO(text), sep=r'\s+', header=None, engine='python')
        return df.astype(np.float64)

    # Semicolon delimiter (European CSV: semicolon-separated, comma decimal)
    if ';' in sample:
        text = '\n'.join(l.replace(',', '.') for l in data_lines)
        df = pd.read_csv(StringIO(text), sep=';', header=None)
        return df.astype(np.float64)

    # Standard delimiter detection
    if '\t' in sample:
        delimiter = '\t'
    elif ',' in sample:
        delimiter = ','
    else:
        delimiter = r'\s+'

    if delimiter == r'\s+':
        df = pd.read_csv(filepath, sep=delimiter, header=None,
                          engine='python', skiprows=skip_count)
    else:
        df = pd.read_csv(filepath, sep=delimiter, header=None,
                          skiprows=skip_count)

    # Convert columns to numeric, coercing errors
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Drop rows that are entirely NaN (failed header lines)
    df = df.dropna(how='all').reset_index(drop=True)

    return df.astype(np.float64)


def read_txt_file(filepath, delimiter=',', header=None):
    try:
        return _read_text_to_df(filepath)
    except Exception as e:
        print(f"Read File Err: {e}")
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
    return np.array(wvn, dtype=np.float64)


def load_spectrum_data(filepath):
    """
    Load spectrum data from file.

    Supports: .txt, .csv, .xlsx files
    Auto-detects delimiter and handles European decimal format.

    Returns:
        np.ndarray: Column vector (N, 1) for consistency across the workflow
    """
    try:
        if filepath.endswith('.xlsx') or filepath.endswith('.xls'):
            df = pd.read_excel(filepath, header=None)
        else:
            df = _read_text_to_df(filepath)

        # Format check
        if df.shape[0] == 1 and df.shape[1] > 1:
            return df.values.flatten().reshape(-1, 1).astype(np.float64)

        if df.shape[1] == 1:
            return df.iloc[:, 0].to_numpy().reshape(-1, 1).astype(np.float64)

        if df.shape[1] == 2:
            return df.iloc[:, 1].to_numpy().reshape(-1, 1).astype(np.float64)

        return df.iloc[:, 1:].mean(axis=1).to_numpy().reshape(-1, 1).astype(np.float64)

    except Exception as e:
        raise ValueError(f"Failed to read spectrum file: {e}")
