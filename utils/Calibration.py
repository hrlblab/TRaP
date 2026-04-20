import numpy as np
import matplotlib.pyplot as plt
import scipy.io
from tkinter import Tk, filedialog
from datetime import datetime
import pandas as pd
from scipy.sparse import diags
from scipy.linalg import cholesky, solve
from scipy.signal import correlate

# Import external custom functions (ensure these are available in your environment)
from utils.accuratePeak import accuratepeak2
from utils.lsqpolyfit import lsqpolyfit
from utils.lsqpolyval import lsqpolyval
from utils.savgol import savgol_filter


class SpectrumCalibration:
    def __init__(self, wc_type):
        self.wc_type = wc_type
        # Predefined wavenumber libraries
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
        # Reference library for Naphthalene (used in Fingerprint mode)
        self.naph_library = np.array([
            3056.4, 1576.6, 1464.5, 1382.2,
            1147.2, 1021.6, 763.8, 513.8
        ])
        # Expected number of peaks for interactive selection
        self.near_num = 7  # Neon‐Argon
        self.acet_num = 4  # Acetaminophen  
        self.w2 = 4

        # Matching indices
        self.nearX = np.array([11, 12, 14, 17, 18, 28, 34])
        self.acetFP = np.array([15, 14, 13, 12])

        # Data storage for processed channels
        self.channel_neon = {}
        self.channel_acet = {}
        self.channel_naph = {}
        # Polynomial coefficients from Neon-Argon processing (used for Acetaminophen calibration)
        self.P_neon = None

    @staticmethod
    def read_spectral_file(title):
        """Open dialog to select spectral data file. If file has two columns, use the second column"""
        root = Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(title=title, filetypes=[('Data files', '*.asc *.txt *.csv')])
        if not file_path:
            raise ValueError("No file selected!")
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
        """Baseline correction using asymmetric least squares smoothing"""
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
        """Normalize data to [0, 1] range"""
        return (data - np.min(data)) / (np.max(data) - np.min(data))

    @staticmethod
    def interactive_peak_selection(spectrum, num_peaks, window=3, title="Select Peaks"):
        """
        Interactive peak selection: Display spectrum and let user click approximate positions.
        Returns arrays of peak positions and corresponding intensities.
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
        Construct kernel function: Assign peak heights at selected positions,
        zeros elsewhere
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
        Alignment using cross-correlation to determine starting position
        """
        padding_length = len(spectrum) - len(kernel)
        padded_kernel = np.pad(kernel, (0, padding_length), mode='constant')
        correlation = np.correlate(spectrum, padded_kernel, mode='full')
        start = np.argmax(correlation) - len(spectrum) - 5 + 1
        return correlation, start

    @staticmethod
    def detect_peaks(spectrum, window_size, threshold):
        """Sliding window local maxima detection (0-based indices)"""
        detected = np.zeros(len(spectrum), dtype=int)
        for ii in range(window_size, len(spectrum) - window_size):
            local_region = spectrum[ii - window_size:ii + window_size + 1]
            if spectrum[ii] == np.max(local_region) and spectrum[ii] >= threshold:
                detected[ii] = ii
        peaks = detected[detected != 0]
        return peaks

    @staticmethod
    def compute_peak_span(spectrum, peaks, sg_window=5, polyorder=1):
        """Calculate peak spans using Savitzky-Golay filtered data"""
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
        """Subpixel-accurate peak detection using accuratepeak2"""
        peaks = peaks + 1  # Convert to 1-based indexing
        x_axis = np.arange(1, len(spectrum) + 1)
        subpixel = accuratepeak2(x_axis, spectrum.reshape(1, -1), peaks, spans)
        return subpixel

    @staticmethod
    def polynomial_calibration(peak_pixels, ref_wavenumbers, poly_order=3):
        """Polynomial fitting for wavenumber calibration using least squares"""
        P = lsqpolyfit(peak_pixels, ref_wavenumbers, None, poly_order)
        fitted, _ = lsqpolyval(P, peak_pixels)
        return P, fitted

    @staticmethod
    def save_calibration(cal_dict, filename):
        """Save calibration data as MATLAB .mat file"""
        scipy.io.savemat(filename, {'Cal': cal_dict})
        print(f"Calibration data saved to {filename}")

    def process_neon(self):
        """
        Neon-Argon processing workflow (Channel 1):
          1. Read and normalize spectrum (no baseline correction)
          2. Interactive peak selection (7 peaks)
          3. Cross-correlation alignment
          4. Threshold-iterative peak detection
          5. Savitzky-Golay filtering and subpixel peak detection
          6. Reference library matching and polynomial fitting
          7. Store results and polynomial coefficients for Acetaminophen
        """
        print("Processing Neon-Argon channel...")
        # 1. Read and normalize
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

        # 2. Interactive peak selection
        peak_pos, peak_heights = self.interactive_peak_selection(norm_spec, self.near_num,
                                                                 title="Select peaks for Neon-Argon")
        channel = {}
        channel['New_pos_Ker'] = peak_pos
        channel['New_hgts_Ker_int'] = peak_heights
        kernel = self.construct_kernel(peak_pos, peak_heights)
        channel['Kernel'] = kernel

        # 3. Cross-correlation alignment
        norm_spec = norm_spec.flatten()
        kernel = kernel.flatten()
        corr, start = self.cross_correlation_alignment(norm_spec, kernel)
        channel['correlation'] = corr
        channel['start'] = start

        # 4. Peak detection with threshold iteration
        channel['threshold'] = 0.001
        channel['w2'] = 3
        channel['iterLim'] = int(1e5)
        channel['newPeakLim'] = self.near_num
        spectrum_size = len(norm_spec)
        d = np.zeros(spectrum_size, dtype=int)
        count = 0
        while True:
            d = np.zeros(spectrum_size, dtype=int)
            for ii in range(channel['w2'], spectrum_size - channel['w2']):
                window_vals = norm_spec[ii - channel['w2']: ii + channel['w2'] + 1]
                if norm_spec[ii] == np.max(window_vals) and norm_spec[ii] >= channel['threshold']:
                    d[ii] = ii
            detected = np.nonzero(d)[0]
            if len(detected) > 0:
                unique_detected = detected[np.insert(np.diff(detected) > 1, 0, True)]
            else:
                unique_detected = detected
            reduced = np.vstack((unique_detected, norm_spec[unique_detected])).T
            low_idx = np.argmax(reduced[:, 0] > start) + 1
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

        # 5. Filtering and subpixel calculation
        y = norm_spec.reshape(1, -1)
        z, _ = savgol_filter(y, 5, 1, 1)
        channel['z'] = z
        spans, _ = self.compute_peak_span(norm_spec, unique_detected, sg_window=5, polyorder=1)
        subpixel_peaks = self.compute_subpixel_peaks(norm_spec, unique_detected, spans)
        channel['subpixel'] = subpixel_peaks

        # 6. Polynomial fitting and error calculation
        ref_wavenumbers = self.neon_argon_library[self.nearX]
        newfitpks = np.column_stack((subpixel_peaks[low_idx - 1:high_idx], ref_wavenumbers[:]))
        channel['newfitpks'] = newfitpks
        P, fitted = self.polynomial_calibration(newfitpks[:, 0], newfitpks[:, 1], poly_order=3)
        error = fitted - ref_wavenumbers
        error = np.squeeze(error)

        # Handle duplicate peaks
        for ii in range(len(subpixel_peaks)):
            for jj in range(len(newfitpks[:, 0])):
                if subpixel_peaks[ii] == newfitpks[jj, 0]:
                    subpixel_peaks[ii] = 1e6
                    subpixel_peaks = np.sort(subpixel_peaks)

        # Update reference library
        for ii in range(len(self.neon_argon_library)):
            for jj in range(len(newfitpks[:, 1])):
                if self.neon_argon_library[ii] == newfitpks[jj, 1]:
                    self.neon_argon_library[ii] = 1e6
        self.neon_argon_library = np.sort(self.neon_argon_library)

        # Filter invalid peaks
        exclude = (subpixel_peaks > len(norm_spec)) & (subpixel_peaks < 1e6)
        subpixel_peaks = subpixel_peaks[~exclude]

        # Sort peaks by intensity
        sorted_indices = np.argsort(
            -norm_spec[np.floor(subpixel_peaks[subpixel_peaks < 1e6]).astype(int)])

        # Error processing
        min_err_temp_avgLambda = np.mean(np.abs(error))
        for ii in range(len(sorted_indices)):
            alpha = subpixel_peaks[sorted_indices[ii]]
            if alpha < 1e6:
                for jj in range(len(self.neon_argon_library)):
                    if self.neon_argon_library[jj] < 1e6:
                        fit_pks = np.append(newfitpks, [[alpha, self.neon_argon_library[jj]]], axis=0)
                        P = lsqpolyfit(fit_pks[:, 0], fit_pks[:, 1], None, 3)
                        new_wvn_fit, _ = lsqpolyval(P, fit_pks[:, 0])
                        err = new_wvn_fit - fit_pks[:, 1]
                        if np.mean(np.abs(err)) > 0.1:
                            continue
                        else:
                            newfitpks = fit_pks
                            self.neon_argon_library[jj] = 1e6
                            break
                        min_err_temp_avgLambda = np.mean(np.abs(err))

        # Final polynomial fit
        P = lsqpolyfit(newfitpks[:, 0], newfitpks[:, 1], None, 3)
        abs_Wvnaxis, _ = lsqpolyval(P, np.arange(1, len(norm_spec) + 1))
        predictwvn, _ = lsqpolyval(P, newfitpks[:, 0])
        abs_error = predictwvn - newfitpks[:, 1]
        error = np.squeeze(abs_error)
        channel['P'] = P
        channel['error'] = error
        channel['min_err_temp_avgLambda'] = min_err_temp_avgLambda
        channel['normalized'] = norm_spec
        self.channel_neon = channel
        self.P_neon = P
        return channel

    def process_acet(self):
        """
        Acetaminophen processing workflow (Channel 2):
          1. Read and baseline correct spectrum
          2. Interactive peak selection (4 peaks)
          3. Cross-correlation alignment
          4. Threshold-iterative peak detection
          5. Savitzky-Golay filtering and subpixel detection
          6. Calibration using Neon-Argon polynomial
        """
        print("Processing Acetaminophen channel...")
        # 1. Read and preprocess
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

        # 2. Interactive peak selection
        peak_pos, peak_heights = self.interactive_peak_selection(norm_spec, self.acet_num,
                                                                 title="Select peaks for Acetaminophen")
        channel = {}
        channel['New_pos_Ker'] = peak_pos
        channel['New_hgts_Ker_int'] = peak_heights
        kernel = self.construct_kernel(peak_pos, peak_heights)
        channel['Kernel'] = kernel

        # 3. Cross-correlation alignment
        norm_spec = norm_spec.flatten()
        kernel = kernel.flatten()
        corr, start = self.cross_correlation_alignment(norm_spec, kernel)
        channel['correlation'] = corr
        channel['start'] = start

        # 4. Peak detection with threshold iteration
        channel['threshold'] = 0.001
        channel['w2'] = 4
        channel['iterLim'] = int(2e5)
        channel['newPeakLim'] = self.acet_num
        spectrum_size = len(norm_spec)
        d = np.zeros(spectrum_size, dtype=int)
        max_iterations = channel['iterLim']
        count = 0
        while count < max_iterations:
            d = np.zeros(spectrum_size, dtype=int)
            for ii in range(channel['w2'], spectrum_size - channel['w2']):
                window_vals = norm_spec[ii - channel['w2']: ii + channel['w2'] + 1]
                if norm_spec[ii] == np.max(window_vals) and norm_spec[ii] >= channel['threshold']:
                    d[ii] = ii
            detected = np.nonzero(d)[0]
            if len(detected) > 0:
                unique_detected = detected[np.insert(np.diff(detected) > 1, 0, True)]
            else:
                unique_detected = detected
            reduced = np.vstack((unique_detected, norm_spec[unique_detected])).T
            low_idx = np.argmax(reduced[:, 0] > start) + 1
            end_value = start + (peak_pos[-1] - peak_pos[0]) if len(peak_pos) > 0 else start
            high_idx = np.argmax(reduced[:, 0] >= end_value) + 1
            New = reduced[low_idx - 1: high_idx]
            if len(New) > channel['newPeakLim']:
                channel['threshold'] += 0.0001
            else:
                break
            count += 1
        if count >= max_iterations:
            print("Acetaminophen: Maximum iterations reached")
        channel['New'] = New

        # 5. Filtering and subpixel calculation
        y = norm_spec.reshape(1, -1)
        z, _ = savgol_filter(y, 5, 1, 1)
        channel['z'] = z
        spans, _ = self.compute_peak_span(norm_spec, unique_detected, sg_window=5, polyorder=1)
        subpixel_peaks = self.compute_subpixel_peaks(norm_spec, unique_detected, spans)
        channel['subpixel'] = subpixel_peaks

        # 6. Calibration using Neon-Argon polynomial
        acet_wavenumbers = self.acetaminophen_library[self.acetFP]
        newfitpks = np.column_stack((subpixel_peaks[low_idx - 1:high_idx], acet_wavenumbers[:]))
        channel['newfitpks'] = newfitpks
        P = self.P_neon
        fitted, _ = lsqpolyval(P, newfitpks[:, 0])
        error = (1e7 / 785) - fitted - newfitpks[:, 1]

        # Secondary threshold iteration
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
            d = d + 1  # Convert to 1-based indexing
            subpixel_peaks = accuratepeak2(np.arange(1, len(spectrum_corr) + 1), spectrum, d, spans)

        # Post-processing
        for ii in range(len(subpixel_peaks)):
            for jj in range(len(newfitpks[:, 0])):
                if subpixel_peaks[ii] == newfitpks[jj, 0]:
                    subpixel_peaks[ii] = 1e6
                    subpixel_peaks = np.sort(subpixel_peaks)

        # Update reference library
        for ii in range(len(self.neon_argon_library)):
            for jj in range(len(newfitpks[:, 1])):
                if self.neon_argon_library[ii] == newfitpks[jj, 1]:
                    self.neon_argon_library[ii] = 1e6
        self.neon_argon_library = np.sort(self.neon_argon_library)

        # Filter invalid peaks
        exclude = (subpixel_peaks > len(norm_spec)) & (subpixel_peaks < 1e6)
        subpixel_peaks = subpixel_peaks[~exclude]

        # Sort peaks by intensity
        sorted_indices = np.argsort(
            -norm_spec[np.floor(subpixel_peaks[subpixel_peaks < 1e6]).astype(int)])

        # Error processing
        lmbda = np.zeros(len(newfitpks[:, 0]))
        for kk in range(len(newfitpks[:, 0])):
            lmbda[kk] = 1e7 / (fitted[0, kk] + newfitpks[kk, 1])
        lmbda = lmbda[lmbda != 0]
        min_err_temp_avglambda = np.mean(lmbda)

        # Wavelength matching
        for ii in range(len(sorted_indices)):
            alpha = subpixel_peaks[sorted_indices[ii]]
            if alpha < 1e6:
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
                            self.acetaminophen_library[jj] = 1e6
                            break

        # Final processing
        unsorted_indices = lmbda > 0
        lambda_acet_unsort = lmbda[unsorted_indices]
        lambda_ref = lmbda
        lmbda = lmbda[lmbda != 0]
        unsort_a_ind = lmbda > 0
        lambda_acet_unsort = lmbda[unsort_a_ind]
        lambda_acet = lambda_acet_unsort

        channel['z'] = z
        channel['newfitpks'] = newfitpks
        channel['subpixel'] = subpixel_peaks
        channel['error'] = np.squeeze(error)
        channel['lambda_acet'] = lambda_acet_unsort
        self.channel_acet = channel
        return channel

    def process_naph(self):
        """
        Naphthalene processing workflow (Fingerprint mode only):
          1. Read and normalize spectrum
          2. Threshold-iterative peak detection
          3. Savitzky-Golay filtering and subpixel detection
          4. Reference library matching
          5. Combine results with Acetaminophen for final calibration
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

        # Peak detection
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
            print("Naphthalene: Max iterations reached")

        # Filtering and span calculation
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

        # Library matching
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

        # Combine results
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

        # Save calibration data
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

        # Plot results
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
        """Main workflow: Process Neon-Argon then Acetaminophen, add Naphthalene if in Fingerprint mode"""
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