### ===========================================================================
### Written by Cayla Dedrick
### new_get_hfr, autofocus_step taken with few changes from newauto.py
### Last updated 20210803
### ===========================================================================

import numpy as np

import utils
# from sep_extract import sep_extract, get_hfr

def leave_one_out_fit(x, y, logger=None):
    '''
    TODO: Docstring
    '''

    best_focus = None
    best_fit = None
    fit_flag = np.zeros_like(x)

    nanind = np.where(np.isnan(x))[0]
    fit_flag[nanind] = np.nan

    try:
        coeffs0, rss0, rank, singular_values, rcond = np.polyfit(x, y, 2, full=True)
    except:
        if logger != None and best_focus == None: logger.error('Quadratic fit failed.')
        return None, None, np.ones_like(x) + fit_flag

    while True:

        good = np.where(fit_flag == 0)[0]
        n = len(good)

        fit = np.polyval(coeffs0, x[good])
        redchi = rss0 / (n - 2)

        chi2_list = np.zeros_like(x)
        coeffs = np.zeros((len(x), 3))

        for i in range(len(x)):
            if fit_flag[i] == 1:
                chi2_list[i] *= np.nan
                coeffs[i] *= np.nan
            else:
                rm_ind = np.delete(good, np.where(good == i)[0])
                rm_x = x[rm_ind]
                rm_y = y[rm_ind]

            try:
                coeff, rss, rank, singular_values, rcond = np.polyfit(rm_x, rm_y, 2, full=True)
            except:
                chi2_list[i] *= np.nan
                coeffs[i] *= np.nan
                continue

            if len(rss) == 0:
                rss = np.nan
            chi2_list[i] = rss / (n - 1 - 2)
            coeffs[i] = coeff

        if np.isnan(chi2_list).all() or np.nanmax(redchi - chi2_list) < 1 / (n + 1) ** 2:
            break

        ol = np.nanargmax(redchi - chi2_list)

        fit_flag[ol] = 1
        coeffs0 = coeffs[ol]
        rss0 = chi2_list[ol] * (n - 1 - 2)

    if coeffs0[0] <= 0:
        if logger!= None: logger.error('Fit upside down quadratic')
        best_focus = None
    else:
        best_focus = int(-coeffs0[1] / (2.0 * coeffs0[0]))

    return best_focus, coeffs0, fit_flag

def get_real_af(r, b):
    '''
    Identify which of the sources that SExtract finds is the correct one

    Inputs:
        r - array of radii
        b - array of fluxes
    Output:
        Index of the correct source

    '''
    r = r / np.min(r)
    b = b / np.max(b)
    if np.argmin(r) == np.argmax(b):
        return np.argmin(r)
    else:
        return np.argmax(b + 1/r)

def new_get_hfr(catfile, fau = False, telescope = None, min_stars = 10, ellip_lim=0.66):
    '''
    TODO: Docstring
    '''

    #S get a dictionary containg the columns of a sextracted image
    cata = utils.readsexcat(catfile)

    if not ('FLUX_RADIUS' in cata.keys()):
        if telescope != None: telescope.logger.exception('No hfr in ' + catfile)
        return np.nan, np.inf, 0

    if len(cata['FLUX_RADIUS']) == 0:
        if telescope != None: telescope.logger.warning('No stars in image')
        return np.nan, np.inf, 0

    if not ('A_IMAGE' in cata.keys() and 'B_IMAGE' in cata.keys()):
        if telescope != None: telescope.logger.error('No major/minor axes in ' + catfile)
        circ_ind = []
        return np.nan, np.inf, 0

    else:
        ellip = cata['A_IMAGE']/cata['B_IMAGE']
        circ_ind = np.where( (ellip >= ellip_lim) & (ellip <= 1.0/ellip_lim) )[0]

    # Check if the stars are too elliptical => windy or not stars; don't use for autofocus
    if len(circ_ind) == 0:
        if telescope != None: telescope.logger.error("Stars are too elliptical, can't use " + catfile)
        return np.nan, np.inf, 0

    if fau:
        star_ind = get_real_af(cata['FLUX_RADIUS'], cata['FLUX_ISO'])
        hfr_med = cata['FLUX_RADIUS'][star_ind]
        hfr_std = 1.0
        numstars = 1.0

    # We expect more than MIN_STAR (ten) stars in a normal image
    elif len(circ_ind > min_stars):
        try:
            hfr_med = np.median(cata['FLUX_RADIUS'][circ_ind])
        except:
            if telescope != None: telescope.logger.error("Could not get median value in "+catfile)
            return np.nan, np.inf, 0

        try:
            numstars = len(circ_ind)
            # Get the Median Absolute Deviation, and we'll convert to stddev then stddev of the mean
            hfr_mad = np.median(np.absolute(cata['FLUX_RADIUS'][circ_ind]-np.median(cata['FLUX_RADIUS'][circ_ind])))

            # We assume that our distribution is normal, and convert to stddev.
            # May need to think more about this, as it isn't probably normal.
            #S Recall stddev of the mean = stddev/sqrt(N)
            hfr_std = (hfr_mad*1.4862)/np.sqrt(numstars)
        except:
            if telescope != None: telescope.logger.error("Could not get HFR_STD in "+catfile)
            return np.nan, np.inf, 0

    return hfr_med, hfr_std, numstars

def autofocus_step(control, telescope, newfocus, af_target):
    '''
    Take a fuckin' step, babe

    Inputs -
        control - minerva.control object
        telescope - telescope object
        newfocus - focuser position to take an af image, in mm
        af_target - autofocus target dict
    '''

    status = telescope.getStatus()
    m3port = status.m3.port

    # default (bad) values
    # will be overwritten by good values or serve as flags later
    median = np.nan
    stddev = np.inf
    numstar = 0
    imnum = '9999'

    if newfocus < float(telescope.minfocus[m3port]) or newfocus > float(telescope.maxfocus[m3port]):
        telescope.logger.warning("Focus position (" + str(newfocus) + ") out of range (" + str(telescope.minfocus[m3port]) + "," + str(telescope.maxfocus[m3port]) + ")")
        return median, stddev, numstar, imnum

    telescope.logger.info("moving focuser and waiting")
    if not telescope.focuserMoveAndWait(newfocus,m3port):
        telescope.recoverFocuser(newfocus,m3port)
        telescope.acquireTarget(af_target)

    if af_target['spectroscopy']:
        telescope.logger.info("taking FAU image")
        imagename = control.takeFauImage(af_target,telescope.id)
    else:
        telescope.logger.info("taking image")
        imagename = control.takeImage(af_target,telescope.id)

    try:
        imnum = imagename.split('.')[4]
    except:
        telescope.logger.exception('Failed to save image: "' + imagename + '"')
        return median, stddev, numstar, imnum

    datapath = '/Data/' + telescope.id.lower() + '/' + control.site.night + '/'

### ===========================================================================
### Requires Python 3 or for me to make sep work in Python 2 for us
    # try:
    #     cata = sep_extract(datapath, imagename, logger = telescope.logger)
    #     telescope.logger.debug('Sextractor success on '+catalog)
    # except:
    #     telescope.logger.exception('Sextractor failed on '+catalog)
    #     return median, stddev, numstar, imnum
### ===========================================================================

    try:
        catalog = utils.sextract(datapath,imagename)
        telescope.logger.debug('Sextractor success on '+catalog)
    except:
        telescope.logger.exception('Sextractor failed on '+catalog)
        return median, stddev, numstar, imnum

    median, stddev, numstar = new_get_hfr(catalog, telescope=telescope, fau=af_target['spectroscopy'])
    return median, stddev, numstar, imnum
