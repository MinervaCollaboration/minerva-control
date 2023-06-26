import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys
sys.dont_write_bytecode = True
from minerva_library import control
import ipdb, datetime, time, socket

import numpy as np
import random
from minerva_library import rv_control
from minerva_library import newauto
from minerva_library import utils
from minerva_library import mail
from minerva_library import env
from minerva_library import measure_flexure as flex
from minerva_library.autofocus import autofocus
from minerva_library.propagatingthread import PropagatingThread
from minerva_library.plotweather import plotweather
from minerva_library.plot_autofocus import plot_autofocus

import glob
import subprocess
import os

plt.rcParams['axes.xmargin'] = 0.05
plt.rcParams['axes.ymargin'] = 0.05

if __name__ == '__main__':
    base_directory = '/home/minerva/minerva-control'
    if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
    minerva = control.control('control.ini',base_directory)

    tels = minerva.telescopes  

    for tel in tels:

        brightstars = utils.brightStars()
       	nstars = len(brightstars['dec'])

       	foci = np.zeros(25)
       	alts = np.zeros(25)

       	for i in range(25):
            alt = -999
            while alt < 30:

                ndx = random.randrange(nstars)

                raj2000 = float(brightstars['ra'][ndx])
                decj2000 = float(brightstars['dec'][ndx])
                pmra = float(brightstars['pmra'][ndx])
                pmdec = float(brightstars['pmdec'][ndx])
                ra, dec = tel.starmotion(raj2000, decj2000, pmra, pmdec)

                alt, az = tel.radectoaltaz(ra, dec)
            target = {
                'ra': ra,
                'dec': dec,
                'spectroscopy': True,
                'endtime': datetime.datetime(2100, 1, 1)
                }

            autofocus(minerva, tel.id, exptime=1.0, target=target)
		
            status = tel.getStatus()
            m3port = status.m3.port
            focus = tel.focus[m3port]

            foci[i] = focus
            alts[i] = alt
	
#			ipdb.set_trace()

        # save data
        data = np.transpose([alts, foci])
        header = 'Alt (degrees)\tFocuser position (mm)'
       	np.savetxt(tel.datadir + minerva.site.night + '/alt_focus.txt', data, delimiter='\t',header=header)
		
        # plot data
        plt.figure()
        plt.plot(alts, foci, 'bo')
        plt.xlabel('Alt (degrees)')
        plt.ylabel('Focuser position (mm)')
        plt.savefig(tel.datadir + minerva.site.night + '/flexure_test.png')

        # email the plots?
        img_file = tel.datadir + minerva.site.night + '/flexure_test.png'

        subject = tel.id + ' completed its altitude vs. focus test'
        body = 'If this worked, there should be a plot here.\n\nLove,\nMINERVA'
        try:
            mail.send(subject, body, attachments=[img_file], level='debug')
        except:
            pass

    minerva.logger.info('It worked!')
