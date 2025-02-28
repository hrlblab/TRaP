import numpy as np
from matplotlib import pyplot as plt
from scipy.io import loadmat
from scipy.signal import find_peaks

from utils.lsqpolyfit import lsqpolyfit


def accuratepeak2(x, y, index, n = 5):
    x = np.array(x).flatten()
    y = np.array(y).flatten()
    index = np.array(index, dtype=int).flatten()
    w = np.full(index.shape, 2)  # window = 2*w + 1, thus default n=5
    if isinstance(n, int):
        w = np.full(index.shape, (n // 2))  # Correct calculation of half window size
    else:
        w = np.floor(np.array(n) / 2).astype(int)
    w[w < 2] = 2
    subx = np.zeros_like(index, dtype=float)

    for i, idx in enumerate(index):
        xx = np.arange(idx - w[i], idx + w[i] + 1)
        p = lsqpolyfit(x[xx - 1], y[xx - 1], None, 2)  # Assuming lsqpolyfit can handle None as sy
        top = -1 * p['Coefficients'][1] / (2 * p['Coefficients'][0])  # Transformed x-coordinates
        subx[i] = p['Scale'][0] + p['Scale'][1] * top  # Convert to x-coordinates

    return subx

# data = loadmat('test_data.mat')
# y = data['y'].flatten()
#
# # 生成 x 数据
# x = np.arange(1, len(y) + 1)
#
# # 自动检测峰值
# indices, _ = find_peaks(y, prominence=0.1)  # 调整参数以适应数据
#
# # 使用 accuratepeak2
# n = 5  # 使用5点进行二次拟合
# subx = accuratepeak2(x, y, indices, n)
#
# # 可视化结果
# plt.figure()
# plt.plot(x, y, 'b-', label='Original Data')
# plt.plot(x[indices], y[indices], 'ro', label='Detected Peaks')
# plt.plot(subx, np.interp(subx, x, y), 'kx', label='Adjusted Peak Centers')
# plt.legend()
# plt.title('Peak Adjustment Using accuratepeak2')
# plt.xlabel('x')
# plt.ylabel('y')
# plt.grid(True)
# plt.show()

# x = np.linspace(-10, 10, 500)
#
# # 创建一个包含多个峰值的信号
# y = np.exp(-(x-2)**2) + np.exp(-(x+2)**2) + np.exp(-(x-5)**2)
#
# # 寻找局部最大值作为峰值
# indices, _ = find_peaks(y)
# subx = accuratepeak2(x, y, indices)
# plt.figure(figsize=(10, 6))
# plt.plot(x, y, 'b-', label='Original Signal', linewidth=1.5)
#
# # 在峰值位置绘制垂直线
# for peak_x in subx:
#     plt.axvline(x=peak_x, color='r', linestyle='--', linewidth=1)
#
# # 标记计算得到的峰值位置
# plt.plot(subx, np.interp(subx, x, y), 'ro', markersize=8, label='Identified Peaks')
#
# # 添加图例和标题
# plt.legend()
# plt.title('Peak Detection using Accurate Peak Center Estimation')
# plt.xlabel('X-axis')
# plt.ylabel('Signal Intensity')
#
# # 显示图形
# plt.show()