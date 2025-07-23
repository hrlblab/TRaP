import numpy as np
import utils.savgol, utils.lsqpolyfit, utils.lsqpolyval
WLMax = []
def WLCorrection(WL, Cal_wvn):
    SWL = utils.savgol.savgol_filter(WL, 15, 1, 0)
    Cal_wvlength = 10e-7 / Cal_wvn
    p = utils.lsqpolyfit.lsqpolyfit(WLMax[:, 0], WLMax[:, 1], None, 8)
    true_WL = utils.lsqpolyval.lsqpolyval(p, Cal_wvlength)
    loc = np.searchsorted(Cal_wvlength, 860, side="left")
    NTWL = true_WL / true_WL[loc]
    NWL = SWL / SWL[loc]
    WL_Correction = NTWL / NWL
    return WL_Correction

light_curve_coeff = []
def NISTCorrection(SRM, Cal_wvn):
    SRM_1 = SRM - np.mean(SRM[10:25])
    true_SRM = light_curve_coeff[0] + light_curve_coeff[1] * Cal_wvn + light_curve_coeff[2] * Cal_wvn ^ 2 + light_curve_coeff[3] * Cal_wvn ^ 3 + light_curve_coeff[4] * Cal_wvn ^ 4 + light_curve_coeff[5] * Cal_wvn ^ 5
    loc = np.searchsorted(Cal_wvn, 1100, side="left")
    NSRM = SRM_1 / SRM_1[loc]
    NTSRM = true_SRM/true_SRM[loc]
    SRM_correction = NTSRM / NSRM
    SRM_correction = utils.savgol.savgol_filter(SRM_correction, 9, 1, 0)
    return SRM_correction


