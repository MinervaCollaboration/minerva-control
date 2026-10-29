import matplotlib
matplotlib.use('Agg', warn=False)
from matplotlib import pyplot as plt

import utils
import glob
from newauto import new_get_hfr
#from af_utils import window_fit
from af_utils import do_quadfit
from af_utils import quadfit_rlsq
import os
import numpy as np
from astropy.io import fits
import ipdb


files = glob.glob('/Data/t?/n20220503/*autofocus.????.fits')

focus_dict = {}

lasttel = 'None'
lastnum = -1
lastnight = 'None'
lastpath = 'None'
lastra = -99.9
lastdec = -99.9

for file in files:
    path = os.path.dirname(file) + '/'
    filename = os.path.basename(file)
    telescope = filename.split('.')[1]
    imnum = int(filename.split('.')[4])
    night = file.split('/')[3]

    # open the fits file to extract relevant header info
    try:
        hdu = fits.open(file)
        platescale = hdu[0].header['PIXSCALE']
        ra = hdu[0].header['RA']
        dec = hdu[0].header['DEC']
        pos = hdu[0].header['FOCPOS']
    except:
        print('Required header keywords missing')
        continue

    if telescope != lasttel or imnum != lastnum+1 or night != lastnight or file==files[-1] or lastra != ra or lastdec != dec:
        # this is the end of a sequence -- analyze it (if there's enough data)
        if file != files[0] and len(sequence) > 2:

            txt_filename = lastpath + lastnight + '.{}.{:04d}.{:04d}.new_autorecord.txt'.format(lasttel, int(np.min(sequence)), int(np.max(sequence)))
            plot_filename = lastpath + lastnight + '.{}.{:04d}.{:04d}.new_autorecord.png'.format(lasttel, int(np.min(sequence)), int(np.max(sequence)))

            header = 'Column 1\tImage Number\nColumn2\tFocuser Position'
            save_data = np.vstack((sequence, pos_list, fwhm_list))
            np.savetxt(txt_filename, save_data, header = header, delimiter='\t')
            best_pos, best_focus = do_quadfit(None, pos_list, fwhm_list)
            coeffs = quadfit_rlsq(pos_list, fwhm_list)

            if best_focus != None:

                x = np.linspace(pos_list.min() - 300, pos_list.max() + 300)
                y = coeffs[0] * x ** 2 + coeffs[1] * x + coeffs[2]
                plt.clf()
                plt.plot(pos_list, fwhm_list, 'bo')
                plt.plot(x, y, 'b--')
                plt.vlines(best_pos, np.nanmin(fwhm_list) - 1.5, np.nanmax(fwhm_list) + 1, 'r',
                           label = 'Best focus = {}'.format(best_pos))
                plt.legend()
                plt.title('{}.{:04d}.{:04d}'.format(telescope, int(np.min(sequence)), int(np.max(sequence))))
                plt.xlim(pos_list.min() - 300, pos_list.max() + 300)
                plt.ylim(np.nanmin(fwhm_list) - 1.5, np.nanmax(fwhm_list) + 1)
                plt.savefig(plot_filename, bbox_inches = 'tight')
                plt.show()
                ipdb.set_trace
            ipdb.set_trace

        # now reset the arrays for the new sequence
        fwhm_list = np.array([])
        pos_list = np.array([])
        sequence = np.array([])

    lasttel = telescope
    lastnum = imnum
    lastnight = night
    lastpath = path
    lastra = ra
    lastdec = dec

    catfile = filename.split('.fits')[0] + '_new.cat'
    checkfile = filename.split('.fits')[0] + '.check.fits'

    # do the source extraction
    if not os.path.exists(path + catfile):
        catfile2 = utils.sextract(path, filename, sexfile='autofocus.20220503.sex',catfile=catfile,checkfile=checkfile)

    # read in the values
    med, std, num = new_get_hfr(path + catfile, fau=True)

    if not np.isnan(med):
        fwhm_list = np.append(fwhm_list, med * platescale)
        pos_list = np.append(pos_list, pos)
        sequence = np.append(sequence,imnum)
                      
