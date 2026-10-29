import numpy as np
import matplotlib
matplotlib.use('Agg',warn=False)
import matplotlib.pyplot as plt
import pandas as pd
from astropy.io import fits
import sep
from skimage.draw import circle_perimeter

def get_af_source(r, b):
    '''
    
    '''
    r = r / np.min(r)
    b = b / np.max(b)
    if np.argmin(r) == np.argmax(b):
        return np.argmin(r)
    else:
        return np.argmax(b + 1/r)

def get_hfr(cata, fau=False, telescope=None, min_stars=10, ellip_lim=0.33):

    if not ('FLUX_RADIUS' in cata.keys()):
        if telescope != None: telescope.logger.exception('No hfr in '+catfile)
        return np.nan, np.inf, 0

    if len(cata['FLUX_RADIUS']) == 0:
        if telescope != None: telescope.logger.warning('No stars in image')
        return np.nan, np.inf, 0

    ellip = cata['ELLIPTICITY']
    circ_ind = np.where( ellip <= ellip_lim )[0]

    # Check if the stars are too elliptical => windy or not stars; don't use for autofocus
    if len(circ_ind) == 0:
        if telescope != None: 
            telescope.logger.error("Stars are too elliptical, can't use.")
        else: print "Stars are too elliptical, can't use."
        return np.nan, np.inf, 0

    flag_ind = np.where( cata['FLAGS'] == 0 )[0]
    if len(flag_ind) == 0:
        if telescope != None: 
            telescope.logger.error("All stars in image have bad flags, can't use.")
        else: print "All stars in image have bad flags, can't use."
        return np.nan, np.inf, 0

    good_ind = np.intersect1d(circ_ind, flag_ind)
    if len(good_ind) == 0:
        if telescope != None: 
            telescope.logger.error("No circular stars with good flags")
        else: print "No circular stars with good flags"
        return np.nan, np.inf, 0


    if fau:
        r = cata['FLUX_RADIUS'][good_ind]
        flux = cata['FLUX_AUTO'][good_ind]
        ind = get_af_source(r, flux)

        hfr_med = r[ind]
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

def sep_extract(datapath, imagename, plot=False, plotname=None, logger = None, minarea = 100, filter_type='matched', 
                filter_kernel = 'default', deblend_cont=0.25, bs = 256, fs=3):
    
    # load image from fits file
    hdu = fits.open(datapath + imagename)
    data = hdu[0].data.astype(np.float64)
    
    # do background subtraction
    bkg = sep.Background(data, bw=bs, bh=bs, fw=fs, fh=fs)
    data_sub = data - bkg
    
    # set filter kernel if string value given
    if filter_kernel == 'default':
        filter_kernel = np.array([[1,2,1], [2,4,2], [1,2,1]])

 #   elif filter_kernel == 'donut':
 #       donut = np.ones((9, 9), dtype=np.uint8)
 #       donut[circle_perimeter(4, 4, 3)] += 1
 #       donut[circle_perimeter(4, 4, 2)] += 1
 #       donut[circle_perimeter(4, 4, 4)] += 1
 #       filter_kernel = donut

    # extract sources
    objects = sep.extract(data_sub, 1, err=bkg.globalrms, minarea = minarea, filter_type=filter_type, 
                          filter_kernel = filter_kernel, deblend_cont=deblend_cont)
    n = len(objects)
    # print(str(n) + ' objects detected in image')
    if logger!= None: logger.info(str(n) + ' objects detected in image.')

    x = objects['x']
    y = objects['y']
    a = objects['a']              
    b = objects['b']              
    theta = objects['theta']
    flag = objects['flag']

    flagged = np.zeros(n)
    flagged[np.where(flag > 7)[0]] = 1

    cata = {}

    # calculate FLUX_AUTO
    kronrad, krflag = sep.kron_radius(data_sub, x, y, a, b, theta, 3.0)
    flux, fluxerr, fflag = sep.sum_ellipse(data_sub, x, y, a, b, theta, 2.5 * kronrad, subpix=1)
    fflag += krflag

    r_min = 3.5 
    use_circle = np.where(kronrad * np.sqrt(a * b) < r_min)[0]
    cflux, cfluxerr, cflag = sep.sum_circle(data_sub, x[use_circle], y[use_circle], 40, subpix=1)
    flux[use_circle] = cflux
    fluxerr[use_circle] = cfluxerr
    fflag[use_circle] = cflag

    cata['FLUX_AUTO'] = flux
    flagged[np.where(fflag > 7)[0]] = 1

    r, rflag = sep.flux_radius(data_sub, x, y, 6.* a, 0.5, normflux=flux, subpix=5)
    cata['FLUX_RADIUS'] = r
    flagged[np.where(rflag > 7)[0]] = 1

    # calculate XWIN_IMAGE, YWIN_IMAGE
    sig = 2. / 2.35 * r 
    xwin, ywin, xyflag = sep.winpos(data_sub, x, y, sig)
    cata['XWIN_IMAGE'] = xwin
    cata['YWIN_IMAGE'] = ywin
    flagged[np.where(xyflag > 7)[0]] = 1

    # calculate ELLIPTICITY
    ellip = 1 - b/a
    cata['ELLIPTICITY'] = ellip

    cata['FLAGS'] = flagged

    cata_df = pd.DataFrame(cata)

    if plot:
        from matplotlib.patches import Circle

        # plot image
        fig, ax = plt.subplots()
        m, s = np.mean(data_sub), np.std(data_sub)
        im = ax.imshow(data_sub, interpolation='nearest', cmap='gray',
                       vmin=m-s, vmax=m+s, origin='lower')

        # plot an ellipse for each object
        for i in range(n):
            c = Circle (xy=(xwin[i], ywin[i]), radius = r[i])
            c.set_facecolor('none')
            if flagged[i] == 0:
                c.set_edgecolor('limegreen')
            else:
                c.set_edgecolor('red')
            ax.add_artist(c)
        if plotname == None:
            plotname = '.'.join(imagename.split('.')[:-1]) + '.sep.png'
        plt.savefig(datapath + plotname, bbox_inches='tight')
        plt.show()
    
    return cata
