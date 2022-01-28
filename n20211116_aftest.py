import matplotlib

matplotlib.use('Agg')
import sys
sys.dont_write_bytecode = True

import ipdb, datetime, time, socket, random
import numpy as np
import matplotlib.pyplot as plt

from minerva_library import utils, control, af_utils
from minerva_library.autofocus import autofocus 
from minerva_library.propagatingthread import PropagatingThread
from minerva_library.plot_autofocus import plot_autofocus
import glob

def random_bright_target(telescope):
    brightstars = utils.brightStars()
    alt = -999

    while alt < 21:
        nstars = len(brightstars['dec'])
        randind = random.randrange(nstars)

        ra_j2000 = float(brightstars['ra'][randind])
        dec_j2000 = float(brightstars['dec'][randind])
        pmra = float(brightstars['pmra'][randind])
        pmdec = float(brightstars['pmdec'][randind])
        ra, dec = telescope.starmotion(ra_j2000, dec_j2000, pmra, pmdec)
        alt, az = telescope.radectoaltaz(ra, dec)
        if alt > 84:
            continue

    target = {
                'ra' : ra,
                'dec' : dec,
                'spectroscopy': True,
                'endtime': datetime.datetime(2100, 1, 1)
            }
    return target

if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
	minerva = control.control('control.ini', base_directory)

        t1 = minerva.telescopes[0]
        datapath = t1.datadir + t1.night + '/'

    # try the autofocus once to see how that goes
        target = random_bright_target(t1)
        autofocus(minerva, 'T1', exptime=1.0, target = target)

        ipdb.set_trace()

    # plot it to see how it looks
        fnames = glob.glob(datapath + '*autorecord*txt')
        ipdb.set_trace()
        
        af = np.loadtxt(autorecord, skiprows=3)
    
        pos_list = af[:, 1]
        fwhm_list = af[:, 2]
        goodind = np.where(np.logical_not(np.isnan(fwhm_list)))[0]

        plt.plot(pos_list, fwhm_list, 'bo')

        coeff = af_utils.quadfit_rlsq(pos_list, fwhm_list)
        if not np.any(np.isnan(coeff)) and coeff[0] > 0:
            best_focus = int(-coeff[0]/(2 * coeff[1]))
            
            pos = np.linspace(np.min(pos_list) - 200, np.max(pos_list) + 200)
            quad = af_utils.quad(coeff, pos)
            plt.plot(pos, quad, 'b--')
            plt.vlines(best_focus, -1, 20, 'red')
        plt.xlim(np.min(pos_list) - 200, np.max(pos_list) + 200)
        plt.ylim(0, np.nanmax(fwhm_list) * 1.1)
        plt.savefig(datapath + t1.night + '.T1.test.autorecord.png')
        plt.show()

        ipdb.set_trace()

    # now do the bigger test for the flexure
    # and to see if the autofocus holds up robustly
        alt_list = []
        focus_list = []

        c = 0
        while c < 24:
            target = random_bright_target(t1)
            autofocus(minerva, 'T1', exptime=1.0, target = target)
        
            status = t1.getStatus()
            m3port = status.m3.port
            focuser_status = t1.getFocuserStatus(m3port)

            alt = np.rad2deg(status.mount.alt_radian)
            focus_position = focuser_status.position
            alt_list.append(alt)
            focus_list.append(focus_position)
            c += 1
        ipdb.set_trace()

        data = np.array([alt_list, focus_list]).T

        np.savetxt(datapath + t1.night + '.T1.alt_vs_focus.txt')

        plt.plot(alt_list, focus_list, 'bo')
        plt.xlabel('Altitude (Degrees)')
        plt.ylabel('Focuser position (mm)')
        plt.savefig(datapath + 'flex.png')
