import numpy as np


def spectral_bin(start, stop, wvn, spectra, binwidth):
    """
    Bins spectral data into specified width bins between a start and stop wavenumber.

    Parameters:
        start (float): Starting wavenumber for binning.
        stop (float): Stopping wavenumber for binning.
        wvn (np.ndarray): Array of wavenumbers corresponding to the spectra.
        spectra (np.ndarray): Array of spectral data to be binned.
        binwidth (float): Width of each bin.

    Returns:
        np.ndarray: New wavenumbers of the binned spectrum.
        np.ndarray: Binned spectral data.
    """
    # Create bin edges and the new wavenumber axis
    bin_wvn = np.arange(start, stop + binwidth, binwidth)
    new_wvn = np.arange(start + binwidth / 2, stop, binwidth)

    # Initialize the binned spectra array
    bin_spect = np.zeros(len(new_wvn))

    # Bin the spectral data
    for k in range(len(bin_wvn) - 1):
        b1, b2 = bin_wvn[k], bin_wvn[k + 1]
        curr_bin_i = (wvn >= b1) & (wvn < b2)  # Current bin indices
        bin_spect[k] = np.mean(spectra[curr_bin_i])

    return new_wvn, bin_spect