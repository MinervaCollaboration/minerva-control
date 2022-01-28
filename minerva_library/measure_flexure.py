import matplotlib
matplotlib.use('Agg', warn=False)

import numpy as np

import matplotlib.pyplot as plt
import numpy as np
import datetime
import time

import control
import utils
#from sep_extract import sep_extract, get_hfr

from af_utils import new_get_hfr

def flex_step(control, telescope, alt, az = 180, fau = False, timeout=60):

    focus = np.nan
    stddev = np.inf
    numstar = 0
    imnum = '9999'

    camera = utils.getCamera(control, telescope.id)

    if alt > 85 or alt < 20:
        telescope.logger.warning('Altitude {:.1f} out of range (20, 85)'.format(alt))
        return focus, stddev, numstar, imnum

    status = telescope.getStatus()
    
    telescope.logger.info('Moving to alt = {:.1f}'.format(alt))
    telescope.mountGotoAltAz(alt, az)

    telescope.logger.info('Waiting for telescope to finish slew; moving = ' + status.mount.moving)

 # wait for the mount to start moving
    time.sleep(3.0)
    status = telescope.getStatus()

    t0 = datetime.datetime.utcnow()
    elapsedTime = 0.0

    while status.mount.moving == 'True' and elapsedTime < timeout:
        time.sleep(1)
        status = telescope.getStatus()
        elapsedTime = (datetime.datetime.utcnow()-t0).total_seconds()

    if elapsedTime > timeout:
        telescope.logger.warning('Timed out while waiting for telescope to slew.')
        return focus, stddev, numstar, imnum

    telescope.logger.info('Taking image')
    imagename = camera.take_image(objname = 'flex_test', exptime=10, fau=fau)

    try:
        imnum = imagename.split('.')[3]
    except:
        telescope.logger.exception('Failed to save image: "' + imagename + '"')
        return focus, stddev, numstar, imnum

    datapath = '/Data/' + telescope.id.lower() + '/' + control.site.night + '/'

    try:
        catalog = utils.sextract(datapath, imagename)
        telescope.logger.debug('Sextractor succeeded on '+ imagename)
    except:
        telescope.logger.exception('Sextractor failed on '+ imagename)
        return focus, stddev, numstar, imnum

    focus, stddev, numstar = new_get_hfr(catalog, telescope=telescope, fau=fau)

    return focus, stddev, numstar, imnum

def diagnose_flexure(control, telescope):
    alt_list = np.append(np.arange(25, 90, 5), np.arange(25, 85, 5)[::-1])

    focus_list = np.array([])
    stddev_list = np.array([])
    imnum_list = np.array([])
    numstar_list = np.array([])

    telid = telescope.id

    for alt in alt_list:
        focus_meas, stddev, numstar, imnum = flex_step(control, telescope, alt)

        status = telescope.getStatus()

        focus_list = np.append(focus_list, focus_meas)
        stddev_list = np.append(stddev_list, stddev)
        imnum_list = np.append(imnum_list, imnum)
        numstar_list = np.append(numstar_list, numstar)

    datapath = '/Data/' + telescope.id.lower() + '/' + control.site.night + '/'
    plotname = '{}.{}.flex_test.{}.{}.png'.format(control.site.night, telid, imnum_list[0], imnum_list[-1])

    plt.plot(alt_list, focus_list, 'o')
    plt.xlabel('Altitude (degrees)')
    plt.savefig(datapath + plotname, bbox_inches='tight')
    plt.show()

    return alt_list, focus_list
