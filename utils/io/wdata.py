# wdata.py
import os
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

def save_figure(fig, operations, base_dir=".", file_ext="png"):
    filename = generate_filename("figure", operations, file_ext)
    filepath = os.path.join(base_dir, filename)
    # 可以增加调试输出：
    print("Saving figure as:", filepath)
    fig.savefig(filepath)
    return filepath

def save_data(data, prefix,  operations, base_dir=".", file_ext="csv", header=None):
    filename = generate_filename(prefix, operations, file_ext)
    filepath = os.path.join(base_dir, filename)
    print("Saving data as:", filepath)
    if header == None:
        np.savetxt(filepath, data, delimiter=",", header='', comments="")
    else:
        np.savetxt(filepath, data, delimiter=",", header=header, comments="")
    return filepath
