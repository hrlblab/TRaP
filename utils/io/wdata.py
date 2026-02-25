# wdata.py
import os
import hashlib
from datetime import datetime
import numpy as np

def generate_filename(prefix, operations, file_ext):
    if isinstance(operations, list):
        ops_str = "_".join(str(op) for op in operations)
    else:
        ops_str = str(operations)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ops_str}_{timestamp}.{file_ext}"
    return filename.replace(" ", "")

def _safe_filename(prefix, operations, file_ext, base_dir=".", max_path_len=240):
    # Windows path-length safety: if full path is too long, shorten filename.
    prefix_root, _ = os.path.splitext(str(prefix))
    filename = generate_filename(prefix_root, operations, file_ext)
    filepath = os.path.join(base_dir, filename)
    if len(filepath) <= max_path_len:
        return filename

    if isinstance(operations, list):
        ops_str = "_".join(str(op) for op in operations)
    else:
        ops_str = str(operations)
    ops_hash = hashlib.md5(ops_str.encode("utf-8")).hexdigest()[:8]
    short_prefix = prefix_root[:40] if prefix_root else "data"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{short_prefix}_{ops_hash}_{timestamp}.{file_ext}".replace(" ", "")
    filepath = os.path.join(base_dir, filename)

    if len(filepath) > max_path_len:
        short_prefix = short_prefix[:20] if short_prefix else "data"
        filename = f"{short_prefix}_{ops_hash}_{timestamp}.{file_ext}".replace(" ", "")

    return filename

def save_figure(fig, operations, base_dir=".", file_ext="png"):
    filename = _safe_filename("figure", operations, file_ext, base_dir=base_dir)
    filepath = os.path.join(base_dir, filename)
    # 可以增加调试输出：
    print("Saving figure as:", filepath)
    fig.savefig(filepath)
    return filepath

def save_data(data, prefix,  operations, base_dir=".", file_ext="csv", header=None):
    filename = _safe_filename(prefix, operations, file_ext, base_dir=base_dir)
    filepath = os.path.join(base_dir, filename)
    print("Saving data as:", filepath)
    if header == None:
        np.savetxt(filepath, data, delimiter=",", header='', comments="")
    else:
        np.savetxt(filepath, data, delimiter=",", header=header, comments="")
    return filepath
