### ===========================================================================
### Written by Cayla Dedrick
### new_get_hfr, autofocus_step taken with few changes from newauto.py
### Last updated 20211101
### ===========================================================================

import numpy as np
import matplotlib.pyplot as plt
#import ipdb

import utils
from stats import robust_least_squares as rlsq

# from sep_extract import sep_extract, get_hfr

def quad(c, x):
    return c[0] * x ** 2 + c[1] * x + c[2]

def quadfit_rlsq(pos, fwhm, loss = 'soft_l1', f_scale=0.1):
    c0 = np.polyfit(pos, fwhm, 2)
    return rlsq(pos, fwhm, quad, c0, loss, f_scale)

def check_quadfit(telescope, c):
    if np.any(np.isnan(c)):
        if telescope != None: telescope.logger.error('Quadratic fit failed')
    elif c[0] < 0:
        if telescope != None: telescope.logger.error('Fit upside down quadratic')
    else:
        return True
    return False

def do_quadfit(telescope, pos, fwhm, logger=None):

    if logger != None: logger.info("fitting focus points to a parabola with least squares method")
    coeff = quadfit_rlsq(pos, fwhm)
    
    if logger != None: logger.info("checking fit")
    if check_quadfit(telescope, coeff):
        quad_min = int(-coeff[1]/(2*coeff[0]))
        if quad_min > np.min(pos) and quad_min < np.max(pos):
            pos_bestfoc = quad_min
            fwhm_bestfoc = quad(coeff, quad_min)
            if logger != None: logger.info("best fit focus " + str(fwhm_bestfoc) + '" at ' + str(pos_bestfoc) + " microns is good")
        else:
            if logger != None: logger.info("quad_min out of range, returning NaNs")
            pos_bestfoc = np.nan
            fwhm_bestfoc = np.nan
    else:
        if logger != None: logger.info("fit bad, returning NaNs")
        pos_bestfoc = np.nan
        fwhm_bestfoc = np.nan

    return pos_bestfoc, fwhm_bestfoc

# ================================================================================================================

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
        if telescope != None: telescope.logger.error("Stars are too elliptical, can't use " + catfile + "(" + str(ellip)+ ")" )
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

def queue_up(pos_list, fwhm_list, stepsize, best_pos = None):
    if best_pos == None:
        best_pos = pos_list[np.nanargmin(fwhm_list)]
    
    left = len(np.where(pos_list < best_pos)[0])
    right = len(np.where(pos_list > best_pos)[0])

    if left < right:
        return np.min(pos_list) - stepsize 
    elif left > right:
        return np.max(pos_list) + stepsize
    else: 
        fwhm_left = fwhm_list[np.nanargmin(pos_list)]
        fwhm_right = fwhm_list[np.nanargmax(pos_list)]
        if fwhm_left < fwhm_right:
            return np.min(pos_list) - stepsize 
        else:
            return np.max(pos_list) + stepsize

