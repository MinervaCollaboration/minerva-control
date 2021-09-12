import matplotlib
matplotlib.use('Agg', warn=False)

import numpy as np

import matplotlib.pyplot as plt
import numpy as np

import control
import utils
from sep_extract import sep_extract, get_hfr

from af_utils import new_get_hfr

def flex_step(control, telid, alt, az = 180, fau = False):

	telescope = control.getTelescope(telid)
	camera = utils.getCamera(control, telid)

	if alt > 85 or alt < 20:
		telescope.logger.warning('Altitude {:.1f} out of range (20, 85)'.format(alt))
		return np.nan

	telescope.logger.info
	telescope.mountGotoAltAz(alt, az)

	status = telescope.getStatus()
	telescope.logger.info('Waiting for telescope to finish slew; moving = ' + status.mount.moving
	while status.mount.moving:
		time.sleep(0.25)
		status = telescope.getStatus()

	imagename = camera.take_image(objname = 'flex_test', fau=fau)

	try:
        imnum = imagename.split('.')[4]
	except:
	    telescope.logger.exception('Failed to save image: "' + imagename + '"')

	datapath = '/Data/' + telescope.id.lower() + '/' + control.site.night + '/'

    try:
        cata = sep_extract(datapath, imagename, logger = telescope.logger)
        telescope.logger.debug('Sextractor succeeded on '+ imagename)
    except:
        telescope.logger.exception('Sextractor failed on '+ imagename)
        return

	focus, stddev, numstar = get_hfr(cata, telescope=telescope, fau=fau)

	return focus, stddev, numstar, imnum

	def diagnose_flexure(control, telid):
		alt_list = np.append(np.arange(25, 90, 5), np.arange(25, 85, 5)[::-1])
		focus_list = np.array([])
		stddev_list = np.array([])
		imnum_list = np.array([])
		numstar_list = np.array([])

		for alt in alt_list:
			focus_meas, stddev, numstar, imnum = flex_step(control, telid)

			focus_list = np.append(focus_list, focus_meas)
			stddev_list = np.append(stddev_list, stddev)
			imnum_list = np.append(imnum_list, imnum)
			numstar_list = np.append(numstar_list, numstar)

		datapath = '/Data/' + telescope.id.lower() + '/' + control.site.night + '/'
		plotname = '{}.{}.flex_test.{}.{}.png'.format(control.site.night, telid, imnum_list[0], imnum_list[-1])

		plt.plot(alt_list, focus_list)
		plt.savefig(datapath + plotname, bbox_inches='tight')
		plt.show()

		return alt_list, focus_list
