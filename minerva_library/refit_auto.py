import numpy as np
import matplotlib
matplotlib.use('Agg', warn=False)
from matplotlib import pyplot as plt
import pandas as pd
import glob
import os
import ipdb
from astropy.io import fits

import utils
from newauto import new_get_hfr
#from sep_extract import sep_extract, get_hfr
from af_utils import window_fit

def get_af_path(night, tel_num):
    path = '/nas/t' + str(tel_num) + '/' + night + '/'
    return path

def redo_autofocus(night, tel_num):
    print night + ': T' + str(tel_num)
    path = get_af_path(night, tel_num)
    
    try:
        file_list = glob.glob(path + '*FAU.autofocus*.fits')
    except:
        print 'glob failed to get paths for T{}, '.format(tel_num) + night
    
    if len(file_list) == 0:
        return 0, 0
    else:
        print file_list

    # get the image numbers associated with autofocus images
    imnum = np.array([])
    for i in range(len(file_list)):
        imnum = np.append(imnum, int(file_list[i].split('.')[-2]))
    imnum = np.sort(imnum)

    # split into individual autofocuses
    af_sequences = []
    sequence = []
    im0 = imnum[0]
    for i in range(len(imnum)):
        im = imnum[i]
        sequence.append(im)
        if i == len(imnum) - 1:
            af_sequences.append(sequence)
        elif imnum[i+1] - im0 >= 10:
            af_sequences.append(sequence)
            sequence = []
            im0 = imnum[i+1]

#    ipdb.set_trace()
    n_af = 0
    n_succ = 0
    # loop through sequences
    for i in range(len(af_sequences)):
#        ipdb.set_trace()
        n_af += 1
        sequence = np.array(af_sequences[i])
        # do source extraction for all images in sequence
        pos_list = np.array([])
        fwhm_list = np.array([])

        for j in range(len(sequence)):

            # get fits file
            filename = night + '.T' + str(tel_num) + '.FAU.autofocus.{:04d}.fits'.format(int(sequence[j]))
            try:
                hdu = fits.open(path + filename)
            except:
                fwhm_list = np.append(fwhm_list, np.nan)
                pos_list = np.append(pos_list, np.nan)
                continue
                
            # grab platescale and focuser position from the fits header
            try:
                platescale = hdu[0].header['PIXSCALE']
            except:
                platescale = 0.265
            
            try:
                pos = hdu[0].header['FOCPOS']
            except:
                print 'FOCPOS header keyword missing for ' + filename
                pos = np.nan

# ================== sep doesn't work in Python 2=================== 
            ## source extract with sep
            # cata = sep_extract('autofocus/', filename, plot=True)
            # med, std, num = get_hfr(cata, fau = True)
# ==================================================================
#            ipdb.set_trace()
            # source extract with SExtract
            catfile = utils.sextract(path, filename, sexfile = 'autofocus.20210512.sex')
            med, std, num = new_get_hfr(catfile, fau=True)            

            # record the FWHM of the target and the focuser position
            fwhm_list = np.append(fwhm_list, med * platescale)
            pos_list = np.append(pos_list, pos)

        try:
#            ipdb.set_trace()
            best_focus, coeffs = window_fit(pos_list, fwhm_list)
        except:
            continue
        
        txt_filename = path + night + '.T{}.{:04d}.{:04d}.new_autorecord.txt'.format(tel_num, int(np.min(sequence)), int(np.max(sequence)))
        plot_filename = path + night + '.T{}.{:04d}.{:04d}.new_autorecord.png'.format(tel_num, int(np.min(sequence)), int(np.max(sequence)))

        header = 'Column 1\tImage Number\nColumn2\tFocuser Position'
        save_data = np.vstack((sequence, pos_list, fwhm_list))
        np.savetxt(txt_filename, save_data, header = header, delimiter='\t')

        if best_focus != None:

            x = np.linspace(pos_list.min() - 300, pos_list.max() + 300)
            y = coeffs[0] * x ** 2 + coeffs[1] * x + coeffs[2]
            plt.plot(pos_list, fwhm_list, 'bo')
            plt.plot(x, y, 'b--')
            plt.vlines(best_focus, np.nanmin(fwhm_list) - 1.5, np.nanmax(fwhm_list) + 1, 'r', 
                       label = 'Best focus = {}'.format(best_focus))
            plt.legend()
            plt.title('T{}.{:04d}.{:04d}'.format(tel_num, int(np.min(sequence)), int(np.max(sequence))))
            plt.xlim(pos_list.min() - 300, pos_list.max() + 300)
            plt.ylim(np.nanmin(fwhm_list) - 1.5, np.nanmax(fwhm_list) + 1)
            plt.savefig(plot_filename, bbox_inches = 'tight')
            plt.show()

            n_succ += 1

    return n_succ, n_af
        
if __name__ == '__main__':        
    
    nights = np.array([])
    for y in range(2018, 2022):
        for m in range(1, 13):
            for d in range(1, 32):
                night = 'n{}{:02d}{:02d}'.format(y, m, d)
                if os.path.exists(get_af_path(night, 1)) or os.path.exists(get_af_path(night, 2)) or\
                   os.path.exists(get_af_path(night, 3)) or os.path.exists(get_af_path(night, 4)):
                    nights = np.append(nights, night)
    
    total_af = 0
    n_success = 0
    for i in range(len(nights)):
        for tel in range(1, 5):
#            ipdb.set_trace()
            n_s, n_t = redo_autofocus(nights[i], tel)
            if n_t > 0:
                print nights[i] + ': {} autofocuses done, {} fits successful ({:.2f}%)'.format(int(n_t), int(n_s), n_s/n_t * 100)
            total_af += n_t
            n_success += n_s
    ipdb.set_trace()

    per_worked = n_success / total_af * 100
    print '{} autofocuses done in total, {} fits successful ({:.2f}%)'.format(int(total_af), int(n_success), per_worked)
    
    ipdb.set_trace()
