import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.optimize import curve_fit


def subtractBaseline(rawSpect):
    return rawSpect - np.min(rawSpect)


def SpectralResponseCorrection(wlCorr, rawSpect):
    if isinstance(wlCorr, pd.DataFrame):
        wlCorr = wlCorr.values.astype(np.float64)
    wlCorr = wlCorr / np.mean(wlCorr[199:, 0]).astype(np.float64)
    wlggCorrSpec = rawSpect.astype(np.float64) * wlCorr[:, 0]
    return wlggCorrSpec


def CosmicRayRemoval(wlggCorrSpec):  # Update Later
    sprSpect = wlggCorrSpec.astype(np.float64)
    return sprSpect


def Truncate(start, stop, wvnFull, sprSpect):
    if wvnFull.ndim > 1:
        wvnFull = wvnFull.flatten().astype(np.float64)
    trunc = (wvnFull >= start) & (wvnFull <= stop)
    wvn = wvnFull[trunc].astype(np.float64)
    truncSpect = sprSpect[trunc].astype(np.float64)
    return wvn, truncSpect


# def Binning(start, stop, wvn, truncSpect, binwidth=3.5):
#     binWvn = np.arange(start, stop, binwidth, dtype=np.float64)
#     newWvn = np.arange(start + binwidth / 2, stop - binwidth, binwidth, dtype=np.float64)
#     binSpect = np.zeros(len(newWvn), dtype=np.float64)
#     for k in range(len(binWvn) - 1):
#         b1, b2 = binWvn[k], binWvn[k + 1]
#         currBinI = (wvn >= b1) & (wvn < b2)
#         if np.any(currBinI):
#             binSpect[k] = np.mean(truncSpect[currBinI]).astype(np.float64)
#         else:
#             binSpect[k] = np.nan
#     return binSpect, newWvn

def Binning(start, stop, wvn, truncSpect, binwidth=3.5):
    binWvn = np.arange(start, stop, binwidth, dtype=np.float64)
    # 计算每个箱的中心作为新波长
    newWvn = (binWvn[:-1] + binWvn[1:]) / 2.0
    binSpect = np.zeros(len(newWvn), dtype=np.float64)
    for k in range(len(newWvn)):
        b1, b2 = binWvn[k], binWvn[k + 1]
        currBinI = (wvn >= b1) & (wvn < b2)
        if np.any(currBinI):
            binSpect[k] = np.mean(truncSpect[currBinI]).astype(np.float64)
        else:
            binSpect[k] = np.nan
    return binSpect, newWvn

def Denoise(binSpect, SGorder=2, SGframe=7):
    spect = savgol_filter(binSpect.astype(np.float64), SGframe, SGorder)
    return spect.astype(np.float64)

def FluorescenceBackgroundSubtraction(spect, polyorder):
    base = baselinePolynomialFit(spect.astype(np.float64), polyorder)
    finalSpect = spect.astype(np.float64) - base
    return base.astype(np.float64), finalSpect.astype(np.float64)

def Normalize(finalSpect):
    finalSpect = finalSpect.astype(np.float64) / np.mean(finalSpect).astype(np.float64)
    return finalSpect


def FinalSpectra(newwvn, spect, base, finalSpect):
    beforeSpect = np.column_stack((newwvn, spect)).astype(np.float64)
    baseSpect = np.column_stack((newwvn, base)).astype(np.float64)
    finalSpect = np.column_stack((newwvn, finalSpect)).astype(np.float64)
    return beforeSpect, baseSpect, finalSpect

def polynomial_model(x, *coeffs):
    return np.polyval(list(coeffs)[:], x)

def curfit3(ref, degree):
    ref = np.array(ref, dtype=np.float64).flatten()
    lensamp = np.arange(1, len(ref) + 1, dtype=np.float64)
    coeffs, _ = curve_fit(polynomial_model, lensamp, ref, p0=np.ones(degree + 1, dtype=np.float64))

    fitResult = polynomial_model(lensamp, *coeffs)

    # fitResult = np.polyval(coeffs[::-1], lensamp).astype(np.float64)
    # matlab_data = loadmat('fitResult.mat')
    # fitResult_matlab = matlab_data['fitResult'].flatten()
    # difference = np.abs(fitResult_matlab - fitResult)
    # max_difference = np.max(difference)
    # print("Difference:", difference)
    # print("Max Difference:", max_difference)
    # relative_difference = difference / np.abs(fitResult_matlab)
    # print("Max Relative Difference:", np.max(relative_difference))
    # fitResult_manual = manual_polyval(coeffs[::-1], lensamp)
    # print("Difference between manual and np.polyval:", np.max(np.abs(fitResult - fitResult_manual)))
    a, b = 0, 0
    return a, b, fitResult

def manual_polyval(coeffs, x):
    result = np.zeros_like(x, dtype=np.float64)
    for i, c in enumerate(coeffs):
        result += c * (x ** (len(coeffs) - i - 1))
    return result


def baselinePolynomialFit(y, degree):
    x = np.arange(len(y))
    data = y.copy().astype(np.float64)  # Ensure double precision
    oldL = np.float64(1_000_000)
    newL = np.float64(999_999)
    xn = [np.float64(1_000_000)]
    samevalue = 0
    count = 1
    while newL > 1 and newL <= oldL and samevalue < 50:
        oldL = newL
        _, _, fitdata = curfit3(data, degree)
        tempdata = np.minimum(fitdata, data)
        index = (fitdata != tempdata).astype(int)
        xn.append(np.sum(index))
        if count < len(xn):
            newL = xn[count] ** (1 / count)

        if xn[count] == xn[count - 1]:
            samevalue += 1
        else:
            samevalue = 0

        data = tempdata.copy()
        count += 1


    # while newL > 1 and newL <= oldL and samevalue < 50:
    #     oldL = newL
    #     _, _, fitdata = curfit3(data, degree)
    #     tempdata = np.minimum(fitdata.astype(np.float64), data)
    #     index = np.where(fitdata == tempdata, 0, 1)
    #     xn.append(np.sum(index).astype(np.float64))
    #
    #     if count < len(xn):
    #         newL = xn[count] ** (1 / (count - 1))
    #     else:
    #         break
    #
    #     data = tempdata.copy()
    #
    #     if count - 1 < len(xn) and xn[count] == xn[count - 1]:
    #         samevalue += 1
    #     else:
    #         samevalue = 0
    #
    #     count += 1
    return data


def polynomial_fit(x, y, degree):
    coeffs = np.polyfit(x, y, degree)
    p = np.poly1d(coeffs)
    return p(x)

def polynomial_fit3(ref, degree):
    ref = np.array(ref)
    lensamp = np.arange(0, len(ref))
    coeffs = np.polyfit(lensamp, ref, degree)
    fitResult = np.polyval(coeffs, lensamp)
    a = 0
    b = 0
    return a, b, fitResult

def iterative_polynomial_baseline_subtraction(y, degree, max_iter=50, threshold=1):
    x = np.arange(len(y))
    data = y.copy()
    oldL = 1_000_000
    newL = 999_999
    xn = [1_000_000]
    samevalue = 0
    count = 1

    while newL > 1 and newL <= oldL and samevalue < max_iter:
        oldL = newL
        fitdata = polynomial_fit(x, data, degree)
        # fitdata = polynomial_fit3(data, degree)

        # print('fitdata: ', fitdata)

        tempdata = np.minimum(fitdata, data)

        # index = np.isclose(fitdata, tempdata, atol=1e-8)

        index = (fitdata != tempdata).astype(int)
        xn.append(np.sum(index))
        if count < len(xn):
            newL = xn[count] ** (1 / count)

        if xn[count] == xn[count - 1]:
            samevalue += 1
        else:
            samevalue = 0

        data = tempdata.copy()
        count += 1

    return data