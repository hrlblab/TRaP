"""Sub-pixel peak refinement.

Fits a parabola to a short window around each approximate peak and takes its
vertex, which locates a peak to a fraction of a pixel. Used by X-axis
calibration, where a whole-pixel error in a reference line propagates straight
into the wavenumber axis.
"""

import numpy as np

from utils.lsqpolyfit import lsqpolyfit


def accuratepeak2(x, y, index, n=5):
    """Refine peak positions to sub-pixel accuracy.

    Args:
        x: Sample positions (1-based pixel axis, as used by the calibration code).
        y: Spectrum values.
        index: Approximate peak positions, 1-based, one per peak.
        n: Window width per peak — an int for all, or one width per peak. The
            fit uses ``2 * (n // 2) + 1`` samples, with a floor of 5.

    Returns:
        Array of refined positions, same length as ``index``. A peak whose
        parabola is degenerate, or whose vertex lands outside the window it was
        fitted to, is returned at its original position rather than at a
        meaningless extrapolation.
    """
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    index = np.asarray(index, dtype=int).ravel()

    if np.isscalar(n) or np.ndim(n) == 0:
        w = np.full(index.shape, int(n) // 2)
    else:
        w = np.floor(np.asarray(n, dtype=float).ravel() / 2).astype(int)
        if w.size == 1:
            w = np.full(index.shape, int(w[0]))
    w[w < 2] = 2

    subx = np.zeros_like(index, dtype=float)

    for i, idx in enumerate(index):
        # Clamp the window to the spectrum. A peak picked near either end would
        # otherwise index past the array (1-based positions, 0-based storage).
        lo = max(1, idx - w[i])
        hi = min(len(x), idx + w[i])
        xx = np.arange(lo, hi + 1)

        if xx.size < 3:
            subx[i] = float(x[min(max(idx, 1), len(x)) - 1])
            continue

        p = lsqpolyfit(x[xx - 1], y[xx - 1], None, 2)
        # lsqpolyfit returns coefficients as a column vector, one column per
        # fitted series. Flatten before use: indexing it directly yields a
        # length-1 array, and assigning that into a scalar slot below is an
        # error on NumPy 2 (deprecated since 1.25).
        c = np.asarray(p["Coefficients"], dtype=float).ravel()

        if c[0] == 0:                       # straight line: no vertex
            subx[i] = float(x[idx - 1])
            continue

        top = -c[1] / (2.0 * c[0])          # vertex in the scaled coordinate
        pos = float(p["Scale"][0] + p["Scale"][1] * top)

        # A near-flat window puts the vertex far outside the samples it was fit
        # to. That is a failed refinement, not a peak; keep the original pick.
        if not np.isfinite(pos) or pos < x[lo - 1] or pos > x[hi - 1]:
            pos = float(x[idx - 1])
        subx[i] = pos

    return subx
