import numpy as np
from scipy.sparse import diags
from scipy.linalg import cholesky, solve
from scipy.signal import correlate

# Import external custom functions (ensure these are available in your environment)
from utils.accuratePeak import accuratepeak2
from utils.lsqpolyfit import lsqpolyfit
from utils.lsqpolyval import lsqpolyval
from utils.savgol import savgol_filter

class XAxisCalibration:
    def __init__(self):
        super().__init__()
        self.neon_xdata = None
        self.neon_ydata = None
        self.neon_spectrum = None
        self.neon_argon_library = None
        self.acetaminophen_library = None
        self.channel_neon = None
        self.P_neon = None

    def choose_neon_library(self, config):
        # if config == 'neon':
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


    def process_neon(self, xdata, ydata, neon_spectrum):
        self.neon_xdata = xdata
        self.neon_ydata = ydata
        self.neon_spectrum = neon_spectrum
        norm_spec = self.normalize(self.neon_spectrum)

        channel = {}
        channel['New_pos_Ker'] = self.neon_xdata
        channel['New_hgts_Ker_int'] = self.neon_ydata
        kernel = self.construct_kernel(self.neon_xdata, self.neon_ydata)
        channel['Kernel'] = kernel

        # Cross Correlation Alignment
        norm_spec = norm_spec.flatten()
        kernel = kernel.flatten()
        corr, start = self.cross_correlation_alignment(norm_spec, kernel)
        channel['correlation'] = corr
        channel['start'] = start

        # Peak detection with threshold iteration
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
            end_value = start + (self.neon_xdata[-1] - self.neon_xdata[0])
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

        # Filtering and Subpixel Calculatioin
        y = norm_spec.reshape(1, -1)
        z, _ = savgol_filter(y, 5, 1, 1)
        channel['z'] = z
        spans, _ = self.compute_peak_span(norm_spec, unique_detected, sg_window=5, polyorder=1)
        subpixel_peaks = self.compute_subpixel_peaks(norm_spec, unique_detected, spans)
        channel['subpixel'] = subpixel_peaks

        # Polynomial fitting and error calculation
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

    def process_acet(self, xdata, ydata, acet_spectrum):
