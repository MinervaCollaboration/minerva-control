### ===========================================================================
### Written by Cayla Dedrick as a replacement for newauto.py
### Significant code stolen from newauto.py
### Last updated 20210803
### ===========================================================================

import numpy as np
import matplotlib.pyplot as plt
import subprocess
import ipdb
import warnings
import datetime
import time
import copy
import glob

import utils
import af_utils

def autofocus(control = None, telid = None, num_steps = 5, defocus_step = 0.3,
              target = None, exptime = 15.0, dome_override = False,
              simulate = False, slew = True):
    '''



    Inputs:
        control (obj) - minerva.control object
        telid (str) - ID of desired telescope (e.g. 'T1')
        num_steps  (int) - Initial number of autofocus steps, default 5
        defocus_step (float) - size of defocus_steps in meters, default=0.3
        target (dict) - target dictionary for object we want to focus on,
                        if None, defaults to current telescope position
        exptime (float) - exposure time for autofocus images, default = 15 sec
        dome_override (bool) - if True, overrides dome control
        simulate (bool) - simulating capabilities don't exist yet
        slew (bool) - if False, telescope will not slew

    Returns:
        None
    '''

    if not simulate:

        control.logger.info('Beginning autofocus')
        telescope = utils.getTelescope(control, telid)
        camera = utils.getCamera(control, telid)
        dome = utils.getDome(control, telid)

        # if we have a defined target, use that
        if target != None:

            # make a new "autofocus target" dict
            af_target = copy.deepcopy(target)
            af_target['name'] = 'autofocus'

            # move to correct port
            if 'spectroscopy' in af_target.keys():
                if af_target['spectroscopy']:
                    m3port = telescope.port['FAU']
                else:
                    m3port = telescope.port['IMAGER']
                    af_target['exptime'] = exptime
                    af_target['fauexptime'] = exptime
                    af_target['filter'] = "V"
            else:
                m3port = telescope.port['IMAGER']
                af_target['spectroscopy'] = False
                af_target['exptime'] = exptime
                af_target['fauexptime'] = exptime
                af_target['filter'] = "V"

            control.logger.info('defined af_target')

        # if not, use the current position of the telescope to build a target dict
        else:
            status = telescope.getStatus()

            # get current port
            m3port = status.m3.port
            if m3port == telescope.port['FAU']:
                spectroscopy = True
            else:
                spectroscopy = False
            status = telescope.getStatus()

            # get current ra and dec
            ra = utils.ten(status.mount.ra_2000)
            dec = utils.ten(status.mount.dec_2000)
            slew = False

            af_target = {'name':'autofocus',
                         'exptime':exptime,
                         'fauexptime':exptime,
                         'filter':"V",
                         'spectroscopy':spectroscopy,
                         'ra' : ra,
                         'dec' : dec
                         }
            control.logger.info('defined af_target based on current status of the telescope')

        # set platescale from camera info
        control.logger.info('setting platescale')
        if af_target['spectroscopy']:
            platescale = float(camera.fau.platescale)
        else:
            platescale = float(camera.platescale)

        # set tracking by target dict, or default to ON
        if 'tracking' in af_target.keys(): tracking = af_target['tracking']
        else: tracking = True

        # if telescope isn't initialized, then initialize it
        # if initialization fails, then recover
        control.logger.info("initializing scope")
        if not telescope.isInitialized(tracking = tracking, derotate = (not af_target['spectroscopy'])):
            if not telescope.initialize(tracking = tracking, derotate = (not af_target['spectroscopy'])):
                telescope.recover(tracking = tracking, derotate = (not af_target['spectroscopy']))

        # move to target if necessary, or use current position
        control.logger.info("checking if telescope should slew to target")
        if 'ra' in af_target.keys() and 'dec' in af_target.keys() and slew:
            telescope.acquireTarget(af_target, derotate=(not af_target['spectroscopy']))
        else:
            telescope.logger.info('No ra and dec, using current position')

        # set the datapath to save images
        control.logger.info("setting data path")
        datapath = telescope.datadir + control.site.night + '/'

        # check if abort
        if telescope.abort:
            telescope.logger.info("Autofocus aborted")
            return

        # get current time
        t0 = datetime.datetime.utcnow()

        # if the dome is closed, wait for up to 10 minutes for it to open,
        # checking the status every 30 seconds
        while (not dome.isOpen()) and (not dome_override):
            telescope.logger.info('Enclosure closed; waiting for dome to open')
            timeelapsed = (datetime.datetime.utcnow()-t0).total_seconds()
            if timeelapsed > 600:
                telescope.logger.info('Enclosure still closed after '+\
                                    '10 minutes; skipping autofocus')
                return
            time.sleep(30)

        # get best guess of the focus
        telescope.guessFocus(m3port)
        focus_guess = telescope.focus[m3port]

        control.logger.info("defining initial autofocus steps")

        # step size
        stepsize = defocus_step * 1000

        # start with 5 steps centered at best focus guess
        # add first 5 steps to step queue
        init_steps = focus_guess + (np.linspace(-2, 2, 5) * stepsize)

        queue = init_steps

        pos_list = np.array([])
        fwhm_list = np.array([])
        imnum_list = np.array([])

        # if routine hasn't worked after 10 steps, give up
        while len(pos_list) <= 10:

            # loop through steps in queue
            while len(queue) > 0:

                # first, check if abort == True
                if telescope.abort:
                    telescope.logger.info("Autofocus aborted")
                    return

                # start with step closest to the current position of the focuser
                goto = np.argmin(np.abs(telescope.focus[m3port] - queue))
                newpos = queue[goto]

                median, std, numstars, imnum = af_utils.autofocus_step(control, telescope, newpos, af_target)

                pos_list = np.append(pos_list, newpos)
                fwhm_list = np.append(fwhm_list, median * platescale)
                imnum_list = np.append(imnum_list, str(imnum))

            # get the indices of the non-nan points
            goodind = np.where(np.logical_not(np.isnan(fwhm_list)))[0]

            # if no stars are found in the first pass through, give up
            if len(goodind) == 0:
                telescope.logger.error('No stars in all images; autofocus failed.')
                return

            good_pos = pos_list[goodind]
            good_fwhm = fwhm_list[goodind]

            min_dex = np.nanargmin(good_fwhm)
            best_measured_pos = good_pos[min_dex]

            control.logger.info('fitting quadratic')
            best_fit_pos, coeffs, fit_flag = af_utils.leave_one_out_fit(pos_list, fwhm_list,
                                                                   logger = control.logger)

            if best_fit_pos != None:
                best_pos = best_fit_pos
                in_fit = np.where( fit_flag == 0 )[0]
                good_pos = pos_list[in_fit]
                good_foc = focus_list[in_fit]

            else:
                best_pos = best_measured_pos

            control.logger.info('checking if parabola is well-sampled')
            pts_to_left = len(np.where( good_pos < best_pos )[0])
            pts_to_right = len(np.where( good_pos > best_pos )[0])

            if pts_to_left < 2 or good_fwhm[np.argmin(good_pos)] - np.min(good_fwhm) < 1:
                control.logger.info('adding additional autofocus step at {:.0f} mm'.format(np.min(pos_list) - stepsize))
                queue = np.append(queue, np.min(pos_list) - stepsize)

            if pts_to_right < 2 or good_fwhm[np.argmax(good_pos)] - np.min(good_fwhm) < 1:
                control.logger.info('adding additional autofocus step at {:.0f} mm'.format(np.max(pos_list) + stepsize))
                queue = np.append(queue, np.max(pos_list) + stepsize)

            if len(queue) == 0:
                break

        if best_fit_pos != None:
            # fit succeeded; use best fitted focus
            telescope.focus[m3port] = best_fit_pos
        else:
            # fit failed;
            best_measured_fwhm = np.nanmin(fwhm_list)
            best_measured_pos = pos_list[np.nanargmin(fwhm_list)]
            if best_measured_fwhm < 3.0:
                # if the FWHM of our best step is less than 3'', use that position
                telescope.logger.warning('Autofocus failed, using best measured focus ('\
                                         + str(best_measured_pos) + ',' + str(best_measured_foc) + ')')
                telescope.focus[m3port] = best_measured_pos
            else:
                # if our best step is still bad, use the focus guess
                telescope.logger.warning('Autofocus failed, and best measured focus is bad ('\
                                          + str(best_measured_foc) + '"); using initial focus guess')

        # write the focus position to a text file 
        focname = 'focus.' + telescope.logger_name + '.port' + m3port+'.txt'
        with open(focname,'w') as fname:
            fname.write(str(telescope.focus[m3port]))

        # move to the focus position
        if not telescope.focuserMoveAndWait(telescope.focus[m3port], m3port):
            telescope.recoverFocuser(telescope.focus[m3port], m3port)
            telescope.acquireTarget(af_target)

        # record environment data
        try: alt = str(float(status.mount.alt_radian) * 180.0/math.pi)
        except: alt = '-1'
        rotatorStatus = telescope.getRotatorStatus(m3port)

        try: rotang = str(float(rotatorStatus.position))
        except: rotang = '720'

        try:    tm1 = str(status.temperature.primary)
        except: tm1 = 'UNKNOWN'

        try:    tm2 = str(status.temperature.secondary)
        except: tm2 = 'UNKNOWN'

        try:    tm3 = str(status.temperature.m3)
        except: tm3 = 'UNKNOWN'

        try:    tamb = str(status.temperature.ambient)
        except: tamb = 'UNKNOWN'

        try:    tback = str(status.temperature.backplate)
        except: tback = 'UNKNOWN'

        try:
            if len(imnum_list)==len(pos_list)==len(focus_list)==len(fit_flag):
                ar_filename = '{}.{}.autorecord.port{}.{}.{}.{}.txt'.format(control.site.night, telid, m3port,\
                                                                            af_target['filter'][0], imnum_list[0],\
                                                                            imnum_list[-1])

                autodata = np.array([imnum_list, pos_list, focus_list, fit_flag]).T

                tel_header = '# Guess\tNew\tTM1\tTM2\tTM3\tTamb\tTback\talt\trotang\n'
                tel_info = '{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(focus_guess, best_focus, tm1, tm2, tm3,\
                                                                         tamb, tback, float(alt), rotang)
                with open(ar_filename, 'a') as fd:
                    fd.write(tel_header)
                    fd.write(tel_info)
                    fd.write(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')+'\n')

                data_header = 'Column 1\tImage number\n'+\
                              'Column 2\tFocuser position\n'+\
                              'Column 3\tMedian focus measure\n'\
                              'Column 4\tOutlier flag'
                header = tel_header + tel_info + data_header

                np.savetxt(ar_filename, autodata, fmt='%s', header=header)
            else:
                control.logger.error('mismatch length in autofocus arrays')
        except:
            control.logger.exception('unhandled error in autofocus results.')

        if best_focus == None:
            return

        telescope.logger.info('Updating best focus for port '+str(m3port)+\
                                ' to '+str(telescope.focus[m3port]))
        telescope.logger.info('Finished autofocus')
        return