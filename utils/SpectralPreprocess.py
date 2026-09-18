import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.optimize import curve_fit


def subtractBaseline(rawSpect):
    return rawSpect - np.min(rawSpect)


def SpectralResponseCorrection(wlCorr, rawSpect, wvn=None):
    """Apply the spectral response (white-light) correction factor to a spectrum.

    Accepts either layout of correction data:

    - **Two columns** ``[wavenumber, factor]`` (e.g. a Renishaw ``WLCor_*.txt``).
      The factor is interpolated onto ``wvn`` by wavenumber, so the correction
      file does not have to share the spectrum's grid or sort order. This
      mirrors the reference MATLAB implementation's ``interp1(WL(:,1), WL(:,2), nx)``.
    - **One column** of factors already sampled on the spectrum's own grid
      (e.g. the output of the SRCF wizard step), applied element-wise.

    Args:
        wlCorr: Correction data as a DataFrame or array, in either layout above.
        rawSpect: Spectrum intensities.
        wvn: Wavenumber axis of ``rawSpect``. Required to use the two-column
            layout; without it a two-column input falls back to its last column,
            which is only valid when that column is already grid-aligned.

    Returns:
        The corrected spectrum, same shape as ``rawSpect``.
    """
    if isinstance(wlCorr, pd.DataFrame):
        wlCorr = wlCorr.values
    wlCorr = np.asarray(wlCorr, dtype=np.float64)
    spect = np.asarray(rawSpect, dtype=np.float64)

    if wlCorr.ndim == 2 and wlCorr.shape[1] >= 2 and wvn is not None:
        # [wavenumber, factor] -> align by wavenumber, never by row index.
        ref_wvn = wlCorr[:, 0]
        ref_fac = wlCorr[:, 1]
        order = np.argsort(ref_wvn)
        factor = np.interp(np.asarray(wvn, dtype=np.float64).flatten(),
                           ref_wvn[order], ref_fac[order])
    else:
        factor = wlCorr[:, -1] if wlCorr.ndim == 2 else wlCorr.ravel()

    factor = factor.reshape(-1)
    if factor.shape[0] != spect.reshape(-1).shape[0]:
        raise ValueError(
            f"Correction factor length ({factor.shape[0]}) does not match the "
            f"spectrum ({spect.reshape(-1).shape[0]}). For a two-column "
            f"[wavenumber, factor] file, pass the spectrum's wavenumber axis "
            f"so the factor can be interpolated onto it."
        )

    return spect * factor.reshape(spect.shape)


def CosmicRayRemoval(wlggCorrSpec, method="None", msn_spect=None, params=None,
                     return_mask=False):
    """Remove cosmic ray spikes from a spectrum.

    Defaults to a pass-through so existing callers keep their current behaviour;
    pass ``method`` to enable detection. See :mod:`utils.CosmicRay` for the
    algorithms and their parameters.

    Args:
        wlggCorrSpec: Spectrum intensities.
        method: "None", "Whitaker-Hayes", or "Li-Dai".
        msn_spect: Neighbouring acquisition of the same sample, required by
            "Li-Dai". Without it that method falls back to Whitaker-Hayes.
        params: Algorithm parameters; unknown keys are ignored.
        return_mask: When True, also return the boolean mask of replaced
            samples and the method actually applied.

    Returns:
        The cleaned spectrum, or ``(cleaned, replaced_mask, method_used)`` when
        ``return_mask`` is True.
    """
    from utils.CosmicRay import despike

    cleaned, mask, used = despike(wlggCorrSpec, method=method,
                                  msn_spect=msn_spect, params=params)
    cleaned = cleaned.astype(np.float64)
    if return_mask:
        return cleaned, mask, used
    return cleaned


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

def Binning(start, stop, wvn, truncSpect, binwidth=3.5, return_info=False):
    """Rebin a spectrum onto a uniform wavenumber grid.

    A bin narrower than the detector's local sample spacing can fall between two
    samples and catch nothing. Such interior bins are filled by interpolating
    their neighbours rather than dropped, because dropping them silently returns
    a non-uniform axis — a 1.0 cm-1 request coming back with a mix of 1 and
    2 cm-1 steps — which then misleads every downstream step that works on
    sample index (Savitzky-Golay among them).

    Empty bins at the very edges are still dropped: there is nothing on one side
    to interpolate from, so they lie outside the data's actual coverage.

    Args:
        start, stop: Wavenumber range to cover.
        wvn, truncSpect: Input axis and intensities.
        binwidth: Width of each bin, in wavenumbers.
        return_info: When True, also return a dict describing what happened.

    Returns:
        (binSpect, newWvn), or (binSpect, newWvn, info) when return_info is True.
        `info` carries `n_filled` (interior bins interpolated), `n_edge_dropped`,
        `n_bins`, and `starved` (True when any bin had to be filled, i.e. the
        bin width is finer than the data supports).
    """
    # For integer bin widths, shift grid so midpoints land on whole wavenumbers
    # e.g. binwidth=1, start=2900.4 → grid [2899.5,2900.5,...] → midpoints [2900,2901,...]
    if binwidth == int(binwidth):
        grid_start = round(start) - binwidth / 2.0
    else:
        grid_start = start
    binWvn = np.arange(grid_start, stop + binwidth, binwidth, dtype=np.float64)
    newWvn = (binWvn[:-1] + binWvn[1:]) / 2.0
    binSpect = np.zeros(len(newWvn), dtype=np.float64)
    for k in range(len(newWvn)):
        b1, b2 = binWvn[k], binWvn[k + 1]
        currBinI = (wvn >= b1) & (wvn < b2)
        if np.any(currBinI):
            binSpect[k] = np.mean(truncSpect[currBinI]).astype(np.float64)
        else:
            binSpect[k] = np.nan

    empty = np.isnan(binSpect)
    filled = edge_dropped = 0

    if empty.all():
        info = dict(n_bins=0, n_filled=0, n_edge_dropped=int(empty.sum()), starved=True)
        out = (np.array([], dtype=np.float64), np.array([], dtype=np.float64))
        return out + (info,) if return_info else out

    # Trim empty bins outside the data's coverage, then interpolate what is left.
    good = np.flatnonzero(~empty)
    lo, hi = good[0], good[-1] + 1
    edge_dropped = int(empty[:lo].sum() + empty[hi:].sum())
    binSpect, newWvn, empty = binSpect[lo:hi], newWvn[lo:hi], empty[lo:hi]

    if empty.any():
        filled = int(empty.sum())
        binSpect[empty] = np.interp(newWvn[empty], newWvn[~empty], binSpect[~empty])

    info = dict(n_bins=len(newWvn), n_filled=filled, n_edge_dropped=edge_dropped,
                starved=filled > 0)
    return (binSpect, newWvn, info) if return_info else (binSpect, newWvn)

def Denoise(binSpect, SGorder=2, SGframe=7):
    spect = savgol_filter(binSpect.astype(np.float64), SGframe, SGorder)
    return spect.astype(np.float64)

def FluorescenceBackgroundSubtraction(spect, polyorder, max_iter=50, exclude_mask=None):
    base = baselinePolynomialFit(spect.astype(np.float64), polyorder, max_iter=max_iter,
                                  exclude_mask=exclude_mask)
    finalSpect = spect.astype(np.float64) - base
    return base.astype(np.float64), finalSpect.astype(np.float64)

def Normalize(finalSpect, method='mean'):
    s = finalSpect.astype(np.float64)
    if method == 'max':
        denom = np.max(np.abs(s))
    elif method == 'area':
        denom = np.trapz(np.abs(s))
    else:  # mean
        denom = np.mean(s)
    return s / denom if denom != 0 else s


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


def baselinePolynomialFit(y, degree, max_iter=50, exclude_mask=None):
    data = y.copy().astype(np.float64)
    if exclude_mask is None:
        exclude_mask = np.zeros(len(y), dtype=bool)
    include_mask = ~exclude_mask
    x_all = np.arange(1, len(data) + 1, dtype=np.float64)

    oldL = np.float64(1_000_000)
    newL = np.float64(999_999)
    xn = [np.float64(1_000_000)]
    samevalue = 0
    count = 1

    while newL > 1 and newL <= oldL and samevalue < max_iter:
        oldL = newL

        if include_mask.any():
            # Fit polynomial ONLY to non-excluded points, then evaluate everywhere.
            # This prevents peak regions from distorting the baseline fit.
            x_fit = x_all[include_mask]
            d_fit = data[include_mask]
            try:
                coeffs, _ = curve_fit(polynomial_model, x_fit, d_fit,
                                      p0=np.ones(degree + 1, dtype=np.float64))
                fitdata = polynomial_model(x_all, *coeffs)
            except Exception:
                _, _, fitdata = curfit3(data, degree)
        else:
            _, _, fitdata = curfit3(data, degree)

        tempdata = np.minimum(fitdata, data)
        # Excluded regions: use polynomial value directly (bypass min operation).
        tempdata[exclude_mask] = fitdata[exclude_mask]

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