import numpy as np
import matplotlib.pyplot as plt
import scipy.io
from tkinter import Tk, filedialog
from datetime import datetime
import pandas as pd
from scipy.sparse import diags
from scipy.linalg import cholesky, solve
from scipy.signal import correlate

# 引入外部自定义函数，请确保这些函数在你的环境中可用
from utils.accuratePeak import accuratepeak2
from utils.lsqpolyfit import lsqpolyfit
from utils.lsqpolyval import lsqpolyval
from utils.savgol import savgol_filter


class SpectrumCalibration:
    def __init__(self, wc_type):
        self.wc_type = wc_type
        # 预定义波数库
        self.neon_argon_library = np.array([
            12947.060, 12946.313, 12581.503, 12476.939, 12372.474, 12322.387,
            12290.439, 12099.913, 12097.637, 12047.720, 11953.502, 11936.584,
            11893.138, 11878.703, 11869.932, 11815.641, 11786.276, 11771.132,
            11735.103, 11703.167, 11666.771, 11639.738, 11581.249, 11554.839,
            11536.761, 11518.188, 11488.823, 11400.360, 11388.716, 11323.865,
            11294.500, 11279.600, 11211.390, 11125.240, 10961.346, 10930.551,
            10781.067, 10762.489, 10751.705, 10722.124, 10690.362, 10668.590,
            10609.652, 10571.707, 10541.096, 10488.601, 10474.056, 10354.340,
            10220.243, 9948.210, 9713.060, 9677.994
        ])
        self.acetaminophen_library = np.array([
            3326.6, 3102.4, 3064.6, 2931.1, 1648.4, 1561.5, 1371.5, 1323.9,
            1278.5, 1236.8, 1168.5, 1105.5, 968.7, 857.9, 834.5, 797.2, 710.8,
            651.6, 465.1, 390.9, 329.2, 213.3
        ])
        # 针对 Naphthalene 的参考库（Fingerprint 模式下使用）
        self.naph_library = np.array([
            3056.4, 1576.6, 1464.5, 1382.2,
            1147.2, 1021.6, 763.8, 513.8
        ])
        # 预期交互式选择的峰数
        self.near_num = 7  # Neon‐Argon
        self.acet_num = 4  # Acetaminophen
        self.w2 = 4

        # 匹配
        self.nearX = np.array([11, 12, 14, 17, 18, 28, 34])
        self.acetFP = np.array([15, 14, 13, 12])

        # 存放各通道数据处理结果
        self.channel_neon = {}
        self.channel_acet = {}
        self.channel_naph = {}
        # Neon‐Argon 处理后的多项式系数，将用于 Acetaminophen 校准
        self.P_neon = None

    @staticmethod
    def read_spectral_file(title):
        """弹出对话框选择光谱数据文件，若文件有两列，则取第二列"""
        root = Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(title=title, filetypes=[('Data files', '*.asc *.txt *.csv')])
        if not file_path:
            raise ValueError("未选择文件！")
        if file_path.endswith('.csv'):
            data = pd.read_csv(file_path)
        else:
            data = np.loadtxt(file_path)
        data = np.atleast_2d(data)
        if data.shape[1] == 2:
            spectrum = data[:, 1]
        else:
            spectrum = data.squeeze()
        return spectrum.astype(np.float64)

    @staticmethod
    def baseline(spectrum, lambda_val=1e3, p=1e-5):
        """基线校正函数"""
        m = len(spectrum)
        D = diags([1, -2, 1], [0, 1, 2], shape=(m - 2, m))
        w = np.ones(m)
        for _ in range(10):
            w = w.flatten()
            W = diags(w, 0, shape=(m, m))
            temp = W + lambda_val * (D.T @ D).toarray()
            C = cholesky(temp)
            z = solve(C, solve(C.T, W @ spectrum))
            w = p * (spectrum > z) + (1 - p) * (spectrum < z)
        return z

    @staticmethod
    def normalize(data):
        """归一化到 [0, 1]"""
        return (data - np.min(data)) / (np.max(data) - np.min(data))

    @staticmethod
    def interactive_peak_selection(spectrum, num_peaks, window=3, title="Select Peaks"):
        """
        交互式峰值选择：显示光谱，用户点击选择大致峰位置，在邻域内寻找最大值。
        返回峰位置数组和对应幅值数组。
        """
        plt.figure(figsize=(12, 6))
        plt.plot(spectrum, label="Spectrum")
        plt.title(title)
        plt.legend()
        plt.show(block=False)
        points = plt.ginput(num_peaks)
        plt.close()
        peak_positions = []
        peak_heights = []
        for x, _ in points:
            idx = int(round(x))
            region = spectrum[max(idx - window, 0):min(idx + window + 1, len(spectrum))]
            peak_idx = np.argmax(region) + max(idx - window, 0)
            peak_positions.append(peak_idx)
            peak_heights.append(spectrum[peak_idx])
        return np.array(peak_positions), np.array(peak_heights)

    @staticmethod
    def construct_kernel(peak_positions, peak_heights):
        """
        根据选择的峰位置与幅值构造核函数，
        核函数在峰位置赋值为峰高，其余位置为零
        """
        kernel = []
        for i in range(len(peak_positions) - 1):
            kernel.append(peak_heights[i])
            zeros_count = peak_positions[i + 1] - peak_positions[i] - 1
            kernel.extend(np.zeros(zeros_count))
        kernel.append(peak_heights[-1])
        return np.array(kernel)

    @staticmethod
    def cross_correlation_alignment(spectrum, kernel):
        """
        对齐：利用交叉相关计算光谱与核函数的相关性，确定起始位置
        """
        padding_length = len(spectrum) - len(kernel)
        padded_kernel = np.pad(kernel, (0, padding_length), mode='constant')
        correlation = np.correlate(spectrum, padded_kernel, mode='full')
        start = np.argmax(correlation) - len(spectrum) - 5 + 1
        return correlation, start

    @staticmethod
    def detect_peaks(spectrum, window_size, threshold):
        """
        滑动窗口法检测局部极大值：返回检测到的峰（0-based 索引）
        """
        detected = np.zeros(len(spectrum), dtype=int)
        for ii in range(window_size, len(spectrum) - window_size):
            local_region = spectrum[ii - window_size:ii + window_size + 1]
            if spectrum[ii] == np.max(local_region) and spectrum[ii] >= threshold:
                detected[ii] = ii
        peaks = detected[detected != 0]
        return peaks

    @staticmethod
    def compute_peak_span(spectrum, peaks, sg_window=5, polyorder=1):
        """
        利用 Savitzky–Golay 滤波计算每个峰的宽度（span）以及滤波后的数据
        """
        y = spectrum.reshape(1, -1)
        z, _ = savgol_filter(y, sg_window, polyorder, 1)
        spans = []
        for p in peaks:
            idx = int(p)
            k = idx
            while k > 0 and (z[0][k] - z[0][k - 1]) < 0:
                k -= 1
            kleft = k
            k = idx
            while k < len(z[0]) - 1 and (z[0][k] - z[0][k + 1]) > 0:
                k += 1
            kright = k
            spans.append(kright - kleft)
        return np.array(spans), z

    @staticmethod
    def compute_subpixel_peaks(spectrum, peaks, spans):
        """
        利用外部函数 accuratepeak2 计算亚像素精度峰位置
        """
        peaks = peaks + 1
        x_axis = np.arange(1, len(spectrum) + 1)
        subpixel = accuratepeak2(x_axis, spectrum.reshape(1, -1), peaks, spans)
        return subpixel

    @staticmethod
    def polynomial_calibration(peak_pixels, ref_wavenumbers, poly_order=3):
        """
        利用最小二乘法拟合多项式完成波数校准，返回多项式系数、拟合值和误差
        """
        P = lsqpolyfit(peak_pixels, ref_wavenumbers, None, poly_order)
        fitted, _ = lsqpolyval(P, peak_pixels)
        return P, fitted

    @staticmethod
    def save_calibration(cal_dict, filename):
        """保存校准数据为 MATLAB 格式文件"""
        scipy.io.savemat(filename, {'Cal': cal_dict})
        print(f"校准数据已保存到 {filename}")

    def process_neon(self):
        """
        Neon‐Argon 处理流程（通道1）：
          1. 读取光谱（不做基线校正）并归一化，若峰出现在前200个点，则置为最小值；
          2. 交互式选择预期 7 个峰，构造核函数；
          3. 利用交叉相关确定对齐起始位置；
          4. 采用滑动窗口检测局部峰，并通过迭代调整阈值达到预期峰数；
          5. 计算滤波、峰宽及亚像素峰位置；
          6. 从参考库中配对形成拟合数据，利用最小二乘多项式拟合得到校准参数；
          7. 返回处理结果，同时保存多项式参数供 Acetaminophen 校准使用。
        """
        print("Processing Neon-Argon channel...")
        # 1. 读取光谱和归一化
        spectrum = self.read_spectral_file("Select Neon-Argon spectral file")
        norm_spec = self.normalize(spectrum)
        if np.argmax(norm_spec) <= 200:
            norm_spec[:200] = np.min(norm_spec)
        plt.figure(figsize=(12, 6))
        plt.plot(norm_spec)
        plt.title("Processed Neon-Argon Spectrum")
        plt.show(block=False)
        plt.pause(1)
        plt.close()

        # 2. 交互式选择预期峰
        peak_pos, peak_heights = self.interactive_peak_selection(norm_spec, self.near_num,
                                                                 title="Select peaks for Neon-Argon")
        channel = {}
        channel['New_pos_Ker'] = peak_pos
        channel['New_hgts_Ker_int'] = peak_heights
        kernel = self.construct_kernel(peak_pos, peak_heights)
        channel['Kernel'] = kernel

        # 3. 交叉相关对齐
        norm_spec = norm_spec.flatten()
        kernel = kernel.flatten()
        corr, start = self.cross_correlation_alignment(norm_spec, kernel)
        channel['correlation'] = corr
        channel['start'] = start

        # 4. 峰检测及阈值迭代——不按强度排序，保持原始检测顺序
        channel['threshold'] = 0.001
        channel['w2'] = 3
        channel['iterLim'] = int(1e5)
        channel['newPeakLim'] = self.near_num
        spectrum_size = len(norm_spec)
        # 使用原始检测顺序：直接提取 d 数组中非零的索引（即检测到的峰位置）
        d = np.zeros(spectrum_size, dtype=int)
        count = 0
        while True:
            d = np.zeros(spectrum_size, dtype=int)
            for ii in range(channel['w2'], spectrum_size - channel['w2']):
                window_vals = norm_spec[ii - channel['w2']: ii + channel['w2'] + 1]
                if norm_spec[ii] == np.max(window_vals) and norm_spec[ii] >= channel['threshold']:
                    d[ii] = ii
            # 提取非零检测值，并去除相邻重复（如果相邻差值为1，则只保留第一个）
            detected = np.nonzero(d)[0]
            if len(detected) > 0:
                unique_detected = detected[np.insert(np.diff(detected) > 1, 0, True)]
            else:
                unique_detected = detected
            # 直接用原始数组的顺序作为 reduced 数组，第二列为对应的幅值
            reduced = np.vstack((unique_detected, norm_spec[unique_detected])).T
            # 按原代码切片方式计算 low 和 high
            low_idx = np.argmax(reduced[:, 0] > start) + 1
            # 对于 Neon-Argon，end_value = start + (最后一个交互峰 - 第一个交互峰)
            end_value = start + (peak_pos[-1] - peak_pos[0])
            high_idx = np.argmax(reduced[:, 0] > end_value) + 1
            New = reduced[low_idx - 1: high_idx]
            if len(New) > channel['newPeakLim']:
                channel['threshold'] += 0.0001
            else:
                break
            count += 1
            if count >= channel['iterLim']:
                print("Neon-Argon: Maximum iterations reached")
                break
        channel['New'] = New

        # 5. 计算滤波、峰宽和亚像素峰位置
        y = norm_spec.reshape(1, -1)
        z, _ = savgol_filter(y, 5, 1, 1)
        channel['z'] = z
        spans, _ = self.compute_peak_span(norm_spec, unique_detected, sg_window=5, polyorder=1)
        subpixel_peaks = self.compute_subpixel_peaks(norm_spec, unique_detected, spans)
        channel['subpixel'] = subpixel_peaks

        # 6. 多项式拟合：从参考库中配对波数
        ref_wavenumbers = self.neon_argon_library[self.nearX]
        newfitpks = np.column_stack((subpixel_peaks[low_idx - 1:high_idx], ref_wavenumbers[:]))
        channel['newfitpks'] = newfitpks
        P, fitted = self.polynomial_calibration(newfitpks[:, 0], newfitpks[:, 1], poly_order=3)

        # 计算error
        error = fitted - ref_wavenumbers
        error = np.squeeze(error)  # 确保 error 为 1D 数组

        # 这里开始模版并没有，开始进行改写
        # In case replicant peaks positions
        for ii in range(len(subpixel_peaks)):
            for jj in range(len(newfitpks[:, 0])):
                if subpixel_peaks[ii] == newfitpks[jj, 0]:
                    subpixel_peaks[ii] = 1e6
                    subpixel_peaks = np.sort(subpixel_peaks)

        # Update WvnLibrary
        for ii in range(len(self.neon_argon_library)):
            for jj in range(len(newfitpks[:, 1])):
                if self.neon_argon_library[ii] == newfitpks[jj, 1]:
                    self.neon_argon_library[ii] = 1e6
        self.neon_argon_library = np.sort(self.neon_argon_library)

        # Delete unacceptable values for subpixel
        exclude = (subpixel_peaks > len(norm_spec)) & (subpixel_peaks < 1e6)
        subpixel_peaks = subpixel_peaks[~exclude]

        # Sort Subpixel
        sorted_indices = np.argsort(
            -norm_spec[np.floor(subpixel_peaks[subpixel_peaks < 1e6]).astype(int)])

        # Error process and Wavenumber process
        min_err_temp_avgLambda = np.mean(np.abs(error))

        for ii in range(len(sorted_indices)):
            alpha = subpixel_peaks[sorted_indices[ii]]

            if alpha < 1e6:  # Make sure the peak position are not identified
                for jj in range(len(self.neon_argon_library)):
                    if self.neon_argon_library[jj] < 1e6:
                        fit_pks = np.append(newfitpks, [[alpha, self.neon_argon_library[jj]]], axis=0)
                        P = lsqpolyfit(fit_pks[:, 0], fit_pks[:, 1], None, 3)
                        new_wvn_fit, _ = lsqpolyval(P, fit_pks[:, 0])
                        err = new_wvn_fit - fit_pks[:, 1]
                        if np.mean(np.abs(err)) > 0.1:
                            # If error is larger than threshold value
                            continue
                        else:
                            # If error is acceptable, process this peak
                            newfitpks = fit_pks
                            self.neon_argon_library[jj] = 1e6  # Flag WvnLib Pos that been used
                            break
                        min_err_temp_avgLambda = np.mean(np.abs(err))

        P = lsqpolyfit(newfitpks[:, 0], newfitpks[:, 1], None, 3)
        abs_Wvnaxis, _ = lsqpolyval(P, np.arange(1, len(norm_spec) + 1))
        predictwvn, _ = lsqpolyval(P, newfitpks[:, 0])
        abs_error = predictwvn - newfitpks[:, 1]
        error = np.squeeze(abs_error)  # 计算并存储误差
        channel['P'] = P
        channel['error'] = error
        channel['min_err_temp_avgLambda'] = min_err_temp_avgLambda
        channel['normalized'] = norm_spec  # 保存归一化数据供后续使用
        self.channel_neon = channel
        self.P_neon = P
        return channel

    def process_acet(self):
        """
        Acetaminophen 处理流程（通道2）：
          1. 读取光谱，对数据进行基线校正后归一化，并将前200个数据（若异常）置为0；
          2. 交互式选择预期 4 个峰，构造核函数；
          3. 利用交叉相关确定对齐起始位置；
          4. 采用迭代调整阈值达到预期检测峰数（保持原始检测顺序和切片方式）；
          5. 计算滤波后数据、峰宽和亚像素峰位置；
          6. 根据 wc_type 选择参考波数，并利用 Neon‐Argon 得到的多项式参数对 Acetaminophen 进行校准；
          7. 返回处理结果。
        """
        print("Processing Acetaminophen channel...")
        # 1. 读取光谱、基线校正、归一化；若前200个数据异常则置0
        spectrum = self.read_spectral_file("Select Acetaminophen spectral file")
        baseline_vals = self.baseline(spectrum)
        spectrum_corr = spectrum - baseline_vals
        norm_spec = self.normalize(spectrum_corr)
        if np.any(norm_spec[:200] > 0.3):
            norm_spec[:200] = 0
        plt.figure(figsize=(12, 6))
        plt.plot(norm_spec)
        plt.title("Processed Acetaminophen Spectrum")
        plt.show(block=False)
        plt.pause(1)
        plt.close()

        # 2. 交互式选择预期峰（4个）
        peak_pos, peak_heights = self.interactive_peak_selection(norm_spec, self.acet_num,
                                                                 title="Select peaks for Acetaminophen")
        channel = {}
        channel['New_pos_Ker'] = peak_pos
        channel['New_hgts_Ker_int'] = peak_heights
        kernel = self.construct_kernel(peak_pos, peak_heights)
        channel['Kernel'] = kernel

        # 3. 交叉相关对齐
        norm_spec = norm_spec.flatten()
        kernel = kernel.flatten()
        corr, start = self.cross_correlation_alignment(norm_spec, kernel)
        channel['correlation'] = corr
        channel['start'] = start

        # 4. 峰检测及迭代调整（保持原始检测顺序，采用切片方式）
        channel['threshold'] = 0.001
        channel['w2'] = 4
        channel['iterLim'] = int(2e5)
        channel['newPeakLim'] = self.acet_num
        spectrum_size = len(norm_spec)
        d = np.zeros(spectrum_size, dtype=int)
        max_iterations = channel['iterLim']
        tolerance = 1  # 允许相差1个峰
        count = 0
        while count < max_iterations:
            d = np.zeros(spectrum_size, dtype=int)
            for ii in range(channel['w2'], spectrum_size - channel['w2']):
                window_vals = norm_spec[ii - channel['w2']: ii + channel['w2'] + 1]
                if norm_spec[ii] == np.max(window_vals) and norm_spec[ii] >= channel['threshold']:
                    d[ii] = ii
            # 保持原始检测顺序，提取非零索引并去除相邻重复（差值为1的只保留第一个）
            detected = np.nonzero(d)[0]
            if len(detected) > 0:
                unique_detected = detected[np.insert(np.diff(detected) > 1, 0, True)]
            else:
                unique_detected = detected
            reduced = np.vstack((unique_detected, norm_spec[unique_detected])).T
            # 直接使用原代码切片方式计算 low 和 high：
            low_idx = np.argmax(reduced[:, 0] > start) + 1
            if len(peak_pos) > 0:
                end_value = start + (peak_pos[-1] - peak_pos[0])
            else:
                end_value = start
            high_idx = np.argmax(reduced[:, 0] >= end_value) + 1
            New = reduced[low_idx - 1: high_idx]
            if len(New) > channel['newPeakLim']:
                channel['threshold'] += 0.0001
            else:
                break
            count += 1
        if count >= max_iterations:
            print("Acetaminophen: Maximum iterations reached, results may be inaccurate")
        channel['New'] = New

        # 5. 计算 Savitzky–Golay 滤波结果、峰宽和亚像素峰位置
        y = norm_spec.reshape(1, -1)
        z, _ = savgol_filter(y, 5, 1, 1)
        channel['z'] = z
        spans, _ = self.compute_peak_span(norm_spec, unique_detected, sg_window=5, polyorder=1)
        subpixel_peaks = self.compute_subpixel_peaks(norm_spec, unique_detected, spans)
        channel['subpixel'] = subpixel_peaks

        # 6. 根据 wc_type 选择参考波数并配对；用 Neon‐Argon 多项式参数校准
        acet_wavenumbers = self.acetaminophen_library[self.acetFP]
        newfitpks = np.column_stack((subpixel_peaks[low_idx - 1:high_idx], acet_wavenumbers[:]))
        channel['newfitpks'] = newfitpks
        P = self.P_neon
        fitted, _ = lsqpolyval(P, newfitpks[:, 0])

        # 计算error
        error = (1e7 / 785) - fitted - newfitpks[:, 1]

        if channel['threshold'] != 0.01:
            channel['threshold'] = 0.01
            d = np.zeros(len(spectrum_corr), dtype=int)

            for ii in range(self.w2, len(spectrum_corr) - self.w2):
                if np.max(norm_spec[ii - self.w2:ii + self.w2 + 1]) == norm_spec[ii] and \
                        norm_spec[ii] >= channel['threshold']:
                    d[ii] = ii

            d = d[d != 0]
            y = norm_spec[:, np.newaxis].T
            z, _ = savgol_filter(y, 5, 1, 1)
            spans = np.zeros(len(d))
            for jj, peak_idx in enumerate(d):
                k = peak_idx
                while z[0][k] - z[0][k - 1] < 0 and k > 0:
                    k -= 1
                kleft = k
                k = peak_idx
                while k < len(z[0]) - 1 and z[0][k] - z[0][k + 1] > 0:
                    k += 1
                kright = k
                spans[jj] = kright - kleft
            spectrum_corr = norm_spec.copy()
            d = d + 1
            subpixel_peaks = accuratepeak2(np.arange(1, len(spectrum_corr) + 1), spectrum, d,
                                             spans)

        for ii in range(len(subpixel_peaks)):
            for jj in range(len(newfitpks[:, 0])):
                if subpixel_peaks[ii] == newfitpks[jj, 0]:
                    subpixel_peaks[ii] = 1e6
                    subpixel_peaks = np.sort(subpixel_peaks)

        # Update WvnLibrary
        for ii in range(len(self.neon_argon_library)):
            for jj in range(len(newfitpks[:, 1])):
                if self.neon_argon_library[ii] == newfitpks[jj, 1]:
                    self.neon_argon_library[ii] = 1e6
        self.neon_argon_library = np.sort(self.neon_argon_library)

        # Delete unacceptable values for subpixel
        exclude = (subpixel_peaks > len(norm_spec)) & (subpixel_peaks < 1e6)
        subpixel_peaks = subpixel_peaks[~exclude]

        # Sort Subpixel
        sorted_indices = np.argsort(
            -norm_spec[np.floor(subpixel_peaks[subpixel_peaks < 1e6]).astype(int)])

        # Error process and Wavenumber process
        lmbda = np.zeros(len(newfitpks[:, 0]))
        for kk in range(len(newfitpks[:, 0])):
            lmbda[kk] = 1e7 / (fitted[0, kk] + newfitpks[kk, 1])
        lmbda = lmbda[lmbda != 0]
        min_err_temp_avglambda = np.mean(lmbda)

        for ii in range(len(sorted_indices)):
            alpha = subpixel_peaks[sorted_indices[ii]]

            if alpha < 1e6:  # Make sure the peak position are not identified
                for jj in range(len(self.acetaminophen_library)):
                    if self.acetaminophen_library[jj] < 1e6:
                        acet_fit, _ = lsqpolyval(P, alpha)
                        lambda_exp = 1e7 / (acet_fit + self.acetaminophen_library[jj])
                        if abs(lambda_exp - min_err_temp_avglambda) > 0.2 * np.mean(
                                abs(error)) + 0.015 * np.floor(len(newfitpks) / len(New)):
                            continue
                        else:
                            newfitpks = np.append(newfitpks, [[alpha, self.acetaminophen_library[jj]]],
                                                              axis=0)
                            lmbda = np.append(lmbda, [lambda_exp])
                            self.acetaminophen_library[jj] = 1e6  # Flag WvnLib Pos that been used
                            break
                    unsorted_indices = lmbda > 0
                    lambda_acet_unsorted = lmbda[unsorted_indices]

        lambda_ref = lmbda
        lmbda = lmbda[lmbda != 0]  # Remove zeros
        unsort_a_ind = lmbda > 0  # Got non-zero indices
        lambda_acet_unsort = lmbda[unsort_a_ind]  # Get unsorted Indices
        lambda_acet = lambda_acet_unsort

        channel['z'] = z
        channel['newfitpks'] = newfitpks
        channel['subpixel'] = subpixel_peaks
        channel['error'] = np.squeeze(error)
        channel['lambda_acet'] = lambda_acet_unsorted
        self.channel_acet = channel
        return channel

    def process_naph(self):
        """
        Naphthalene 处理流程（仅在 Fingerprint 模式下使用）：
          1. 选择 Naphthalene 光谱文件，读取数据（若有两列则取第二列）；
          2. 如果前200个数据存在异常，则将其置为最小值；
          3. 采用迭代调整阈值检测峰（类似 Acetaminophen 部分），并利用 Savitzky–Golay 滤波计算峰宽和亚像素峰位置；
          4. 与 Naphthalene 参考波数库匹配，得到配对数据；
          5. 与 Acetaminophen 的结果组合生成最终校准数据，并绘图显示。
        """
        print("Processing Naphthalene channel...")
        spectrum = self.read_spectral_file("Select Naphthalene spectral file")
        norm_spec = self.normalize(spectrum)
        if np.argmax(norm_spec) < 200:
            norm_spec[:200] = np.min(norm_spec)
        plt.figure(figsize=(12, 6))
        plt.plot(norm_spec)
        plt.title("Processed Naphthalene Spectrum")
        plt.show(block=False)
        plt.pause(1)
        plt.close()

        spectrum = norm_spec.flatten()
        d3 = np.zeros(len(spectrum), dtype=int)
        sLength = len(spectrum)
        w2 = 3
        threshold = 0.025
        max_iter = 1000
        count = 0
        while count < max_iter:
            d3 = np.zeros(sLength, dtype=int)
            for ii in range(w2, sLength - w2):
                if spectrum[ii] == np.max(spectrum[ii - w2:ii + w2 + 1]) and spectrum[ii] >= threshold:
                    d3[ii] = ii
            peaks = d3[d3 != 0]
            if len(peaks) > 15:
                threshold += 0.005
            else:
                break
            count += 1
        if count >= max_iter:
            print("Naphthalene: 最大迭代次数到达，请检查文件数据。")
        y = spectrum.reshape(1, -1)
        z, _ = savgol_filter(y, 5, 1, 1)
        spans = []
        for p in peaks:
            idx = int(p)
            k = idx
            while k > 0 and (z[0][k] - z[0][k - 1]) < 0:
                k -= 1
            kleft = k
            k = idx
            while k < len(z[0]) - 1 and (z[0][k] - z[0][k + 1]) > 0:
                k += 1
            kright = k
            spans.append(kright - kleft)
        spans = np.array(spans)
        subpixel = accuratepeak2(np.arange(1, sLength + 1), spectrum.reshape(1, -1), peaks, spans)
        naphfitpks = np.array([[1, 1]])
        lambda_naph = np.zeros(len(subpixel))
        for a in subpixel:
            for j in range(len(self.naph_library)):
                naphfit, _ = lsqpolyval(self.P_neon, a)
                lambda_exp = 1e7 / (naphfit[0, 0] + self.naph_library[j])
                if abs(lambda_exp - np.mean(self.channel_acet['newfitpks'][:, 1])) <= (0.8 + 0.015 * len(naphfitpks)):
                    naphfitpks = np.vstack([naphfitpks, [a, self.naph_library[j]]])
                    lambda_naph[np.where(subpixel == a)[0][0]] = lambda_exp
                    self.naph_library[j] = 1e6
                    break
        naphfitpks = naphfitpks[1:, :]
        WVNaxis_ftpks = np.concatenate([self.channel_acet['newfitpks'][:, 0], naphfitpks[:, 0]])
        lambda_acet_unsort = self.channel_acet['lambda_acet']
        lambda_naph_unsort = lambda_naph[lambda_naph > 0]
        ExWVN_lambda = np.concatenate([lambda_acet_unsort, lambda_naph_unsort])
        indices = np.argsort(WVNaxis_ftpks)
        lambda_graph = np.column_stack((WVNaxis_ftpks[indices], ExWVN_lambda[indices]))
        avg = np.mean(ExWVN_lambda)
        stdev = np.std(ExWVN_lambda)
        count_total = len(ExWVN_lambda)
        Wavelength = np.array([avg, stdev, count_total])
        abs_Wvnaxis, _ = lsqpolyval(self.P_neon, np.arange(1, len(self.channel_neon['normalized']) + 1))
        Wvn = (1e7 / Wavelength[0]) - abs_Wvnaxis
        Cal = {
            'Wvn': Wvn.reshape(-1, 1),
            'Wavelength': Wavelength,
            'CalibrationDate': datetime.now().strftime("%Y-%m-%d"),
            'CalibrationTime': datetime.now().strftime("%H:%M:%S"),
            'AbsWvnAssignments': self.channel_neon['newfitpks'],
            'RelWvnAssignments': lambda_graph,
            'Polynomials': self.P_neon
        }
        filename = f"Cal_Python_{datetime.now().strftime('%Y%m%d')}.mat"
        self.save_calibration(Cal, filename)
        plt.figure(figsize=(10, 8))
        plt.subplot(2, 1, 1)
        sorted_idx = np.argsort(self.channel_neon['newfitpks'][:, 0])
        plt.plot(self.channel_neon['newfitpks'][sorted_idx, 0],
                 np.abs(self.channel_neon['error'][sorted_idx]), 'r.-', markersize=5)
        plt.title(f"Absolute Wavenumber Error and Laser Wavelength\nCalibration saved in {filename}")
        plt.xlabel("Pixel")
        plt.ylabel("Error")
        plt.legend([f"{len(self.channel_neon['newfitpks'][:, 0])} peaks"], loc="upper left")
        plt.subplot(2, 1, 2)
        sorted_lambda = np.argsort(lambda_graph[:, 0])
        plt.plot(lambda_graph[sorted_lambda, 0], lambda_graph[sorted_lambda, 1], 'b.-', markersize=5)
        plt.xlabel("Pixel")
        plt.ylabel("Wavelength (nm)")
        plt.legend([f"{len(lambda_graph[:, 0])} wavelengths"], loc="upper left")
        plt.tight_layout()
        plt.show()
        self.channel_naph = {'newfitpks': naphfitpks, 'lambda_naph': lambda_naph}
        return self.channel_naph

    def run_calibration(self):
        """主流程：先处理 Neon-Argon，再处理 Acetaminophen，如果 wc_type 为 Fingerprint，则处理 Naphthalene"""
        neon = self.process_neon()
        acet = self.process_acet()
        cal_data = {
            'CalibrationDate': datetime.now().strftime("%Y-%m-%d"),
            'CalibrationTime': datetime.now().strftime("%H:%M:%S"),
            'NeonArgon': neon,
            'Acetaminophen': acet
        }
        if self.wc_type == 'Fingerprint':
            naph = self.process_naph()
            cal_data['Naphthalene'] = naph
        filename = f"Cal_Python_{datetime.now().strftime('%Y%m%d')}.mat"
        self.save_calibration(cal_data, filename)
        plt.figure(figsize=(10, 8))
        sorted_idx = np.argsort(neon['newfitpks'][:, 0])
        plt.plot(neon['newfitpks'][sorted_idx, 0],
                 np.abs(neon['error'].flatten()[sorted_idx]), 'r.-', markersize=5)
        plt.title(f"Neon-Argon Absolute Wavenumber Error\nCalibration saved in {filename}")
        plt.xlabel("Pixel")
        plt.ylabel("Error")
        plt.legend([f"{len(neon['newfitpks'][:, 0])} peaks"], loc='upper left')
        plt.show()


if __name__ == "__main__":
    print("Perform Wavenumber Calibration for:")
    print("1: Fingerprint")
    print("2: High-wavenumber")
    print("3: None")
    wc_type_input = input("Choose an option (1, 2, or 3): ").strip()
    wc_type_options = {'1': 'Fingerprint', '2': 'High-wavenumber', '3': 'None'}
    wc_type = wc_type_options.get(wc_type_input, 'None')
    calibration = SpectrumCalibration(wc_type)
    calibration.run_calibration()
