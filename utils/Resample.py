#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebinning a spectrum onto a uniform wavenumber grid.

Every method here is a linear operator: each output point is a weighted sum of
input samples. That is what makes them comparable — the weights decide both the
value and how input noise propagates, so the noise figure reported to the user
is computed from the same weights the resampler actually applies, never from a
table of remembered constants.

Three methods, differing in what they do when the bin width and the detector's
sampling are not matched:

- **Average** — mean of the samples falling inside each bin. Buys signal-to-noise
  when a bin spans several samples (1/sqrt(N)), but a bin narrower than the local
  spacing can fall between two samples and catch nothing; those interior bins are
  filled from their neighbours so the axis stays uniform.
- **Interpolate** — linear interpolation of the original spectrum at each bin
  centre. Handles any bin width without special cases, but reads only the two
  samples bracketing the centre, so it never gains signal-to-noise no matter how
  wide the bin.
- **Integrate** — the mean value of the piecewise-linear interpolant over each
  bin. Reduces to a weighted average when a bin spans many samples and to
  interpolation when it sits between two, with no crossover to special-case. It
  conserves the integral, and weights partially-covered samples by their overlap
  rather than including or excluding them outright. The cost is a slightly wider
  effective kernel than a hard-edged average, so marginally more smoothing.

A grating samples uniformly in wavelength, so in wavenumber the spacing changes
across the window. "Bin width below the sampling" is therefore a local property,
not a global one, which is why `grid_report` reports the range and not just a
mean.
"""

import numpy as np

__all__ = ["VALID_BIN_METHODS", "bin_edges", "resample", "grid_report"]

VALID_BIN_METHODS = ("Average", "Interpolate", "Integrate")


def bin_edges(start, stop, binwidth):
    """Bin edges and centres for the target grid.

    For an integer bin width the grid is shifted so centres land on whole
    wavenumbers (651, 652, ...), which is what makes saved axes readable.
    """
    binwidth = float(binwidth)
    if binwidth == int(binwidth):
        grid_start = round(start) - binwidth / 2.0
    else:
        grid_start = start
    edges = np.arange(grid_start, stop + binwidth, binwidth, dtype=np.float64)
    return edges, (edges[:-1] + edges[1:]) / 2.0


def _keep_mask(edges, x_lo, x_hi):
    """Bins fully inside the data's coverage.

    Shared by every method so switching method never shifts the axis — only the
    values on it.
    """
    return (edges[:-1] >= x_lo) & (edges[1:] <= x_hi)


def _cumulative(x, y):
    """Running integral of the piecewise-linear interpolant, evaluated at x."""
    return np.concatenate(([0.0], np.cumsum(np.diff(x) * (y[:-1] + y[1:]) / 2.0)))


def _integral_to(x, y, cum, t):
    """Integral of the interpolant from x[0] to each point in t."""
    t = np.clip(t, x[0], x[-1])
    i = np.clip(np.searchsorted(x, t) - 1, 0, len(x) - 2)
    x0, x1, y0, y1 = x[i], x[i + 1], y[i], y[i + 1]
    yt = y0 + (y1 - y0) * (t - x0) / (x1 - x0)
    return cum[i] + (t - x0) * (y0 + yt) / 2.0


def _average(x, y, edges, keep):
    """Per-bin mean, with empty interior bins filled from their neighbours."""
    lo = np.searchsorted(x, edges[:-1], side="left")
    hi = np.searchsorted(x, edges[1:], side="left")
    counts = (hi - lo).astype(np.float64)
    csum = np.concatenate(([0.0], np.cumsum(y)))
    totals = csum[hi] - csum[lo]

    vals = np.full(len(counts), np.nan, dtype=np.float64)
    nz = counts > 0
    vals[nz] = totals[nz] / counts[nz]

    vals, counts = vals[keep], counts[keep]
    centres = (edges[:-1] + edges[1:])[keep] / 2.0

    empty = np.isnan(vals)
    n_filled = int(empty.sum())
    if n_filled and not empty.all():
        vals[empty] = np.interp(centres[empty], centres[~empty], vals[~empty])
    return vals, counts, n_filled


def _interpolate(x, y, edges, keep):
    centres = (edges[:-1] + edges[1:])[keep] / 2.0
    return np.interp(centres, x, y)


def _integrate(x, y, edges, keep):
    cum = _cumulative(x, y)
    I = _integral_to(x, y, cum, edges)
    return ((I[1:] - I[:-1]) / np.diff(edges))[keep]


def resample(wvn, spect, start=None, stop=None, binwidth=3.5, method="Average",
             return_info=False):
    """Put a spectrum on a uniform grid of the requested bin width.

    Args:
        wvn, spect: Input axis and intensities, ascending in wavenumber.
        start, stop: Range to cover; defaults to the data's own extent.
        binwidth: Target spacing, in wavenumbers.
        method: One of VALID_BIN_METHODS.
        return_info: Also return a dict describing what the grid did.

    Returns:
        (values, centres), or (values, centres, info) when return_info is True.

    Raises:
        ValueError: On an unknown method, or if nothing survives the grid.
    """
    if method not in VALID_BIN_METHODS:
        raise ValueError(f"Unknown bin method {method!r}. Valid: {VALID_BIN_METHODS}")

    x = np.asarray(wvn, dtype=np.float64).ravel()
    y = np.asarray(spect, dtype=np.float64).ravel()
    order = np.argsort(x)
    if not np.all(order == np.arange(len(x))):
        x, y = x[order], y[order]

    start = x[0] if start is None else float(start)
    stop = x[-1] if stop is None else float(stop)
    edges, _ = bin_edges(start, stop, binwidth)
    keep = _keep_mask(edges, x[0], x[-1])

    if not keep.any():
        raise ValueError(
            f"BinWidth {binwidth:g} cm-1 leaves no complete bin inside the data "
            f"range ({x[0]:.1f}-{x[-1]:.1f} cm-1)."
        )

    centres = ((edges[:-1] + edges[1:]) / 2.0)[keep]
    n_filled = 0
    if method == "Average":
        vals, counts, n_filled = _average(x, y, edges, keep)
    elif method == "Interpolate":
        vals = _interpolate(x, y, edges, keep)
        counts = None
    else:
        vals = _integrate(x, y, edges, keep)
        counts = None

    if not return_info:
        return vals, centres

    # Count what actually landed in each bin, so callers can act on the emptiest
    # one rather than on a ratio against a summary of the spacing.
    lo = np.searchsorted(x, edges[:-1], side="left")[keep]
    hi = np.searchsorted(x, edges[1:], side="left")[keep]
    bin_counts = hi - lo
    counts_min = int(bin_counts.min()) if bin_counts.size else 0
    n_empty = int((bin_counts == 0).sum())

    step = np.diff(x)
    info = dict(
        method=method, n_bins=len(centres), n_filled=n_filled,
        n_dropped_edges=int((~keep).sum()), n_empty=n_empty,
        samples_per_bin=counts_min,
        samples_per_bin_observed_min=counts_min,
        samples_per_bin_worst_ratio=float(binwidth / step.max()),
        samples_per_bin_median=float(binwidth / np.median(step)),
        native_min=float(step.min()), native_median=float(np.median(step)),
        native_max=float(step.max()),
        supersampled=bool(binwidth < step.max()),
        sparse=bool(counts_min < 1),
    )
    return vals, centres, info


# ──────────────────────────────────────────────────────────────────────────
# What the chosen width means on this axis — for the UI readout
# ──────────────────────────────────────────────────────────────────────────
def _noise_factor(x, edges, keep, method):
    """Output noise SD per unit input noise SD, from the actual weights.

    Each output point is a weighted sum of input samples, so for white input
    noise its SD is the 2-norm of that point's weight row. Averaged over bins.
    """
    centres = ((edges[:-1] + edges[1:]) / 2.0)[keep]

    if method == "Interpolate":
        i = np.clip(np.searchsorted(x, centres) - 1, 0, len(x) - 2)
        t = (centres - x[i]) / (x[i + 1] - x[i])
        return float(np.mean(np.sqrt((1 - t) ** 2 + t ** 2)))

    if method == "Average":
        lo = np.searchsorted(x, edges[:-1], side="left")[keep]
        hi = np.searchsorted(x, edges[1:], side="left")[keep]
        n = (hi - lo).astype(np.float64)
        n = n[n > 0]                      # empty bins inherit their neighbours
        return float(np.mean(1.0 / np.sqrt(n))) if n.size else float("nan")

    # Integrate: weights come from integrating the hat functions over each bin.
    lo_e, hi_e = edges[:-1][keep], edges[1:][keep]
    norms = np.empty(len(lo_e))
    for k, (a, b) in enumerate(zip(lo_e, hi_e)):
        i0 = max(np.searchsorted(x, a) - 1, 0)
        i1 = min(np.searchsorted(x, b), len(x) - 1)
        w = {}
        for i in range(i0, i1):
            u, v = max(a, x[i]), min(b, x[i + 1])
            if v <= u:
                continue
            h = x[i + 1] - x[i]
            su, sv = (u - x[i]) / h, (v - x[i]) / h
            w[i] = w.get(i, 0.0) + h * ((sv - sv ** 2 / 2) - (su - su ** 2 / 2))
            w[i + 1] = w.get(i + 1, 0.0) + h * (sv ** 2 / 2 - su ** 2 / 2)
        vals = np.array(list(w.values())) / (b - a)
        norms[k] = np.linalg.norm(vals) if vals.size else np.nan
    return float(np.nanmean(norms))


def grid_report(wvn, binwidth, method="Average", start=None, stop=None):
    """Describe what a bin width does to this particular axis.

    Returns a dict with the grid size, the native spacing range, how many bins
    would carry interpolated rather than measured values, the noise factor the
    method actually delivers, and a one-line `summary` for display.
    """
    x = np.asarray(wvn, dtype=np.float64).ravel()
    x = np.sort(x)
    if x.size < 2:
        return dict(ok=False, summary="Load a spectrum to see grid details.")

    binwidth = float(binwidth)
    if binwidth <= 0:
        return dict(ok=False, summary="BinWidth must be greater than zero.")

    start = x[0] if start is None else float(start)
    stop = x[-1] if stop is None else float(stop)
    edges, _ = bin_edges(start, stop, binwidth)
    keep = _keep_mask(edges, x[0], x[-1])
    if not keep.any():
        return dict(ok=False,
                    summary=f"BinWidth {binwidth:g} leaves no complete bin in range.")

    step = np.diff(x)
    nf = _noise_factor(x, edges, keep, method)

    # Samples per bin is reported at its WORST, not on average. The axis is
    # non-uniform, so whether any bin starves is decided where the samples are
    # sparsest — that is, against the largest spacing. Quoting the median would
    # call a width safe while bins at the sparse end of the axis still catch
    # nothing, and would contradict the advice to set the width above the
    # maximum step.
    spb_min = binwidth / step.max()
    spb_median = binwidth / np.median(step)

    # The figure that decides whether a width is usable is the number of samples
    # actually counted in the emptiest bin — not a ratio against a summary of the
    # spacing. On a non-linear axis one end can sit at one sample per bin while
    # the other is spotty, and only a count sees that. Counts are integers, so
    # "fewer than one sample per bin" and "at least one empty bin" are the same
    # condition.
    lo = np.searchsorted(x, edges[:-1], side="left")[keep]
    hi = np.searchsorted(x, edges[1:], side="left")[keep]
    counts = hi - lo
    n_empty = int((counts == 0).sum())
    counts_min = int(counts.min()) if counts.size else 0
    n_filled = n_empty if method == "Average" else 0

    supersampled = binwidth < step.max()
    sparse = counts_min < 1
    out = dict(ok=True, n_bins=int(keep.sum()),
               samples_per_bin=counts_min,              # what callers should act on
               samples_per_bin_observed_min=counts_min,
               samples_per_bin_worst_ratio=float(spb_min),
               samples_per_bin_median=float(spb_median),
               native_min=float(step.min()), native_median=float(np.median(step)),
               native_max=float(step.max()), noise_factor=nf,
               n_empty=n_empty, n_filled=n_filled,
               supersampled=supersampled, sparse=sparse,
               level="blocked" if sparse else ("caution" if supersampled else "ok"))

    head = (f"{out['n_bins']} bins · min {counts_min} sample(s)/bin · "
            f"noise x{nf:.2f}")
    axis = (f"axis spacing {out['native_min']:.3f}-{out['native_max']:.3f} "
            f"(median {out['native_median']:.3f}) cm-1")
    if sparse:
        out["summary"] = (f"{head} — {n_empty} of {out['n_bins']} bins contain no "
                          f"sample at all. Raise BinWidth above "
                          f"{out['native_max']:.3f} cm-1. {axis}")
    elif supersampled:
        out["summary"] = (f"{head} — narrower than the widest gaps in the axis, so "
                          f"bin contents are uneven across it. {axis}")
    else:
        out["summary"] = f"{head}. {axis}"
    return out


def smallest_safe_binwidth(wvn, start=None, stop=None, hi=None):
    """Narrowest bin width at which every bin still contains a sample.

    Searched rather than derived: the largest step is a lower bound, but whether
    a bin starves also depends on where the grid's edges fall against the
    samples, so the true threshold can sit slightly either side of it.
    """
    x = np.sort(np.asarray(wvn, dtype=np.float64).ravel())
    if x.size < 2:
        return None
    step = np.diff(x)
    lo_w, hi_w = step.min(), float(hi if hi is not None else step.max() * 2)
    for _ in range(40):
        mid = (lo_w + hi_w) / 2
        r = grid_report(x, mid, method="Average", start=start, stop=stop)
        if r.get("ok") and not r["sparse"]:
            hi_w = mid
        else:
            lo_w = mid
    return round(hi_w, 3)
