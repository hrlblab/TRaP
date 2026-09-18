#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cosmic ray (spike) detection and removal.

CCD detectors register cosmic ray strikes as narrow, positive, randomly placed
spikes. Two complementary algorithms are provided, because the information
available differs completely depending on whether a neighbouring acquisition of
the same sample exists.

**Whitaker-Hayes** (single spectrum). Modified Z-score of the first difference.
Differencing removes the baseline and fluorescence entirely, leaving spikes as
extreme outliers against a robust MAD scale. Its discriminator is *narrowness*,
so it needs real Raman bands to be comfortably wider than a strike — check that
assumption against the instrument before trusting it.

    Whitaker, D. A. & Hayes, K. (2018). A simple algorithm for despiking Raman
    spectra. Chemometrics and Intelligent Laboratory Systems, 179, 82-84.

**Li-Dai** (two spectra). Compares the spectrum against a Most Similar
Neighbouring (MSN) spectrum through a linear approximation ``x = a*xm + b``,
which absorbs intensity and fluorescence drift between acquisitions. Detection
does not rely on spike width at all, so it stays valid on low-resolution
instruments where a strike is as wide as a genuine band. Spikes sitting on
strong Raman peaks are separated from real peak variation by a moving-window
correlation test.

    Li, S. & Dai, L. (2011). An improved algorithm to remove cosmic spikes in
    Raman spectra for online monitoring. Applied Spectroscopy, 65(11), 1300-1306.

Both return ``(cleaned_spectrum, replaced_mask)`` so callers can report and plot
exactly which points were altered.
"""

import numpy as np

__all__ = ["whitaker_hayes", "li_dai", "despike", "VALID_COSMIC_METHODS"]

VALID_COSMIC_METHODS = ("None", "Whitaker-Hayes", "Li-Dai")


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────
def _runs(mask):
    """Yield (start, stop_exclusive) for each contiguous True run in mask."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[breaks + 1]))
    stops = np.concatenate((idx[breaks], [idx[-1]])) + 1
    return list(zip(starts.tolist(), stops.tolist()))


def _merge_runs(runs, max_gap):
    """Merge runs separated by at most max_gap samples.

    Li-Dai note the detection zone can break apart: on a decreasing strong peak
    some spike pixels fall under the threshold, and in the derivative residual
    the pixel at the very centre of a spike is always near zero.
    """
    if not runs or max_gap <= 0:
        return runs
    merged = [list(runs[0])]
    for a, b in runs[1:]:
        if a - merged[-1][1] <= max_gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [tuple(r) for r in merged]


def _mad_scale(v):
    """Median absolute deviation, with a fallback when the data are degenerate."""
    med = np.median(v)
    mad = np.median(np.abs(v - med))
    if mad <= 0:
        mad = np.mean(np.abs(v - med))
    return med, (mad if mad > 0 else np.nan)


def _local_linear_replace(x, xa, zone, nr, replaced):
    """Li-Dai recovery: rescale xa onto x using nr normal pixels either side.

    Fitting locally rather than pasting xa in wholesale keeps the repaired
    segment continuous with its neighbours.
    """
    lo, hi = zone
    n = len(x)
    left, right, i = [], [], lo - 1
    while i >= 0 and len(left) < nr:
        if not replaced[i]:
            left.append(i)
        i -= 1
    i = hi
    while i < n and len(right) < nr:
        if not replaced[i]:
            right.append(i)
        i += 1

    anchors = np.array(sorted(left + right), dtype=int)
    if anchors.size >= 2 and np.ptp(xa[anchors]) > 0:
        a, b = np.polyfit(xa[anchors], x[anchors], 1)
        x[lo:hi] = a * xa[lo:hi] + b
    elif anchors.size >= 1:
        # Not enough spread to fit a slope — fall back to a flat interpolation
        # across the zone, which is still better than leaving the spike.
        x[lo:hi] = np.interp(np.arange(lo, hi), anchors, x[anchors])
    replaced[lo:hi] = True


# ──────────────────────────────────────────────────────────────────────────
# Whitaker-Hayes — single spectrum
# ──────────────────────────────────────────────────────────────────────────
def whitaker_hayes(spect, z_thresh=15.0, max_width=3, fill_window=5):
    """Despike one spectrum via the modified Z-score of its first difference.

    Args:
        spect: 1-D intensities.
        z_thresh: Modified Z-score above which a difference counts as a spike.
            Raise it when genuine bands are only a few pixels wide.
        max_width: Widest run of flagged samples still treated as a strike.
            Wider runs are released as real Raman bands.
        fill_window: Half-width of the neighbourhood averaged to repair a point.

    Returns:
        (cleaned, replaced_mask)
    """
    y = np.asarray(spect, dtype=np.float64).ravel().copy()
    replaced = np.zeros(y.size, dtype=bool)
    if y.size < 3:
        return y, replaced

    dy = np.diff(y)
    med, mad = _mad_scale(dy)
    if not np.isfinite(mad):
        return y, replaced           # flat spectrum: nothing to detect

    z = 0.6745 * (dy - med) / mad
    flagged = np.abs(z) > float(z_thresh)

    # A spike at sample i shows up in both adjacent differences.
    cand = np.zeros(y.size, dtype=bool)
    cand[:-1] |= flagged
    cand[1:] |= flagged

    # A strike spanning k samples flags the k+1 differences that bracket it, so
    # its candidate run is k+2 samples wide. Compare against that, not k, or
    # max_width silently means "k - 2".
    for lo, hi in _runs(cand):
        if hi - lo > int(max_width) + 2:
            continue                 # too wide to be a strike — a real band
        replaced[lo:hi] = True

    if not replaced.any():
        return y, replaced

    w = int(fill_window)
    clean_idx = np.flatnonzero(~replaced)
    for lo, hi in _runs(replaced):
        near = clean_idx[(clean_idx >= lo - w) & (clean_idx < hi + w)]
        if near.size == 0:
            near = clean_idx
        if near.size == 0:
            replaced[lo:hi] = False  # nothing clean to draw on; leave as-is
            continue
        y[lo:hi] = np.interp(np.arange(lo, hi), near, y[near])

    return y, replaced


# ──────────────────────────────────────────────────────────────────────────
# Li-Dai — spectrum vs. most similar neighbouring spectrum
# ──────────────────────────────────────────────────────────────────────────
def li_dai(spect, msn_spect, rp=0.33, t=5.0, w=3, Rt=0.6, tr=4.0, nr=3,
           polyorder=5, fbs_maxiter=50, max_gap=2, narrow_zone=3):
    """Despike one spectrum against a neighbouring acquisition of the same sample.

    Parameter names follow the paper. Defaults are its Table III (industrial
    online application) values, which is the more conservative of the two sets
    it reports; Table I (simulation) uses t=1.7, Rt=0.8, tr=6, nr=2, rp=0.3.
    Thresholds are instrument-specific and should be calibrated before use.

    Args:
        spect: 1-D intensities of the spectrum being cleaned.
        msn_spect: The Most Similar Neighbouring spectrum — another acquisition
            of the same sample. Must be the same length as ``spect``.
        rp: Partition ratio defining the strong-Raman-peak (SRP) areas, as a
            fraction of the fluorescence-subtracted maximum.
        t: Intensity threshold on the scaled residual for spike detection.
        w: Window size for the moving-window correlation analysis.
        Rt: Correlation threshold below which an SRP-area zone is a spike.
        tr: Intensity threshold on the scaled derivative residual, used to
            shrink an SRP-area zone down to the spike itself.
        nr: Number of neighbouring normal pixels each side used to fit the
            local linear replacement.
        polyorder, fbs_maxiter: Passed to the iterative polynomial baseline fit
            used to locate the SRP areas.
        max_gap: Samples of separation still merged into one detection zone.
        narrow_zone: A detection zone this wide or narrower inside an SRP area
            is taken as a spike without running the correlation test. The test
            reads shape, and correlation is scale-invariant, so a spike landing
            on a peak apex leaves a 3-point window's shape intact and slips
            through. A zone only a few pixels wide is already the narrowness
            signature the paper relies on — genuine peak-intensity variation
            spreads across the whole band, which is why the zones in the paper
            run tens of pixels wide.

    Returns:
        (cleaned, replaced_mask)

    Raises:
        ValueError: If ``msn_spect`` has a different length than ``spect``.
    """
    from utils.SpectralPreprocess import baselinePolynomialFit

    x = np.asarray(spect, dtype=np.float64).ravel().copy()
    xm = np.asarray(msn_spect, dtype=np.float64).ravel()
    replaced = np.zeros(x.size, dtype=bool)

    if xm.size != x.size:
        raise ValueError(
            f"MSN spectrum length ({xm.size}) does not match the spectrum "
            f"({x.size}). Li-Dai compares two acquisitions point by point; "
            f"they must share a wavenumber axis."
        )
    if x.size < max(5, int(w) + 2):
        return x, replaced

    # (1) SRP areas, from the fluorescence-subtracted spectrum.
    base = baselinePolynomialFit(x, int(polyorder), max_iter=int(fbs_maxiter))
    fs = x - base
    im = fs.max()
    srp = fs > im * float(rp) if im > 0 else np.zeros(x.size, dtype=bool)

    # (2) Linear approximation of the current spectrum from its neighbour.
    if np.ptp(xm) <= 0:
        return x, replaced
    a, b = np.polyfit(xm, x, 1)
    xa = a * xm + b

    # (3) Scaled absolute residual, and the detection zones above threshold.
    res = x - xa
    s = res.std()
    if s <= 0:
        return x, replaced
    r = np.abs(res) / s

    zones = _merge_runs(_runs(r > float(t)), int(max_gap))
    if not zones:
        return x, replaced

    # Derivative residual, used to shrink zones that sit on strong peaks.
    xd, xda = np.diff(x), np.diff(xa)
    dres = xd - xda
    sxd = dres.std()
    rd = np.abs(dres) / sxd if sxd > 0 else np.zeros(dres.size)

    w = max(2, int(w))
    for lo, hi in zones:
        on_srp = srp[lo:hi].any()

        if not on_srp:
            # zw — no strong peak here, so the excursion is a spike outright.
            _local_linear_replace(x, xa, (lo, hi), int(nr), replaced)
            continue

        # zs — could be a spike, or just a strong band changing intensity.
        if hi - lo <= int(narrow_zone):
            # Too narrow to be peak-intensity variation; skip the shape test,
            # which cannot see a spike sitting on a peak apex anyway.
            _local_linear_replace(x, xa, (lo, hi), int(nr), replaced)
            continue

        # Pad symmetrically by at least one window either side. The paper's
        # zones are tens of pixels wide because strong peaks drift between
        # online acquisitions; against a replicate they collapse to the spike
        # itself, and a one-sided pad would leave every window straddling the
        # zone edge instead of centred on it.
        pad = max(w, 2)
        clo, chi = max(0, lo - pad), min(x.size, hi + pad)
        if chi - clo < w:
            continue

        rc = []
        for i in range(clo, chi - w + 1):
            xw, xaw = x[i:i + w], xa[i:i + w]
            if np.ptp(xw) <= 0 or np.ptp(xaw) <= 0:
                continue
            rc.append(np.corrcoef(xw, xaw)[0, 1])
        if not rc or np.nanmin(rc) >= float(Rt):
            continue                 # genuine strong-peak variation — leave it

        # Confirmed spike on a strong peak: shrink the zone to the spike
        # itself using the derivative residual, then repair.
        seg = slice(max(0, lo - 1), min(rd.size, hi))
        inner = _merge_runs(_runs(rd[seg] > float(tr)), int(max_gap))
        if inner:
            off = seg.start
            for ilo, ihi in inner:
                _local_linear_replace(x, xa, (off + ilo, min(off + ihi + 1, x.size)),
                                      int(nr), replaced)
        else:
            _local_linear_replace(x, xa, (lo, hi), int(nr), replaced)

    return x, replaced


# ──────────────────────────────────────────────────────────────────────────
# dispatch
# ──────────────────────────────────────────────────────────────────────────
def despike(spect, method="None", msn_spect=None, params=None):
    """Dispatch to the requested despiking algorithm.

    Falls back to Whitaker-Hayes when Li-Dai is asked for but no neighbouring
    spectrum is available, so a batch containing a lone file still gets cleaned
    rather than silently skipped.

    Returns:
        (cleaned, replaced_mask, method_actually_used)
    """
    y = np.asarray(spect, dtype=np.float64).ravel()
    params = dict(params or {})
    method = str(method or "None")

    if method == "None":
        return y.copy(), np.zeros(y.size, dtype=bool), "None"

    if method == "Li-Dai":
        if msn_spect is None:
            method = "Whitaker-Hayes"
        else:
            keep = ("rp", "t", "w", "Rt", "tr", "nr", "polyorder", "fbs_maxiter", "max_gap")
            cleaned, mask = li_dai(y, msn_spect,
                                   **{k: v for k, v in params.items() if k in keep})
            return cleaned, mask, "Li-Dai"

    if method == "Whitaker-Hayes":
        keep = ("z_thresh", "max_width", "fill_window")
        cleaned, mask = whitaker_hayes(y, **{k: v for k, v in params.items() if k in keep})
        return cleaned, mask, "Whitaker-Hayes"

    raise ValueError(f"Unknown cosmic ray method {method!r}. "
                     f"Valid: {VALID_COSMIC_METHODS}")
