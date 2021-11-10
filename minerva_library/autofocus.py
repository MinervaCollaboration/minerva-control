### ===========================================================================
### Written by Cayla Dedrick as a replacement for newauto.py
### Significant code stolen from newauto.py
### Last updated 20211101
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

def autofocus(control, telid, num_steps = 5, defocus_step = 0.3,
              target = None, exptime = 15.0, dome_override = False,
              slew = True, test = False, simulate = False):
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

        # if we have a defined target, use it
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
                af_target['filter'] = 'V'
            else:
                m3port = telescope.port['IMAGER']
                af_target['spectroscopy'] = False
                af_target['exptime'] = exptime
                af_target['fauexptime'] = exptime
                af_target['filter'] = 'V'

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

        if test:
            ipdb.set_trace()

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
            telescope.logger.info('No ra and dec in target dict, using current position')

        # set the datapath to save images
        control.logger.info("setting data path")
        datapath = telescope.datadir + control.site.night + '/'

        # check if abort
        if telescope.abort:
            telescope.logger.info("Autofocus aborted")
            return

        if test:
            ipdb.set_trace()

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

        # step size in mm
        stepsize = defocus_step * 1000

        # start with 5 steps centered at best focus guess
        # add first 5 steps to step queue
        init_steps = focus_guess + (np.linspace(-2, 2, 5) * stepsize)

        pos_list = np.array([])
        fwhm_list = np.array([])
        imnum_list = np.array([])

        queue = init_steps

#====================================================================================
# Start of autofocus loop
#====================================================================================

        while len(pos_list) <= 10:             # if routine hasn't worked after 10 steps, give up
            while len(queue) > 0:              # loop through steps in queue 
                # first, check if abort == True
                if telescope.abort:
                    telescope.logger.info("Autofocus aborted")
                    return

                focuserStatus = telescope.getFocuserStatus(m3port)
                focuser_pos = float(focuserStatus.position)

                # start with step closest to the current position of the focuser
                goto = np.argmin(np.abs(focuser_pos - queue))
                new_focuser_pos = queue[goto]

                median, std, numstars, imnum = af_utils.autofocus_step(control, telescope, new_focuser_pos, af_target)

                if test:
                    ipdb.set_trace()

                pos_list = np.append(pos_list, new_focuser_pos)
                fwhm_list = np.append(fwhm_list, median * platescale)
                imnum_list = np.append(imnum_list, str(imnum))

                queue = np.delete(queue, goto)

                if test:
                    focuserStatus = telescope.getFocuserStatus(m3port)
                    print(new_focuser_pos)
                    print(focuserStatus.position)
                    ipdb.set_trace()


            # get the indices of the non-nan points
            goodind = np.where(np.logical_not(np.isnan(fwhm_list)))[0]

            # if no stars are found in the first pass through, give up
            if len(goodind) == 0:
                telescope.logger.error('No stars in all images; autofocus failed.')
                return

            poslist_good = pos_list[goodind]
            fwhmlist_good = fwhm_list[goodind]

            mindex = np.argmin(fwhmlist_good)
            best_measured_focus = (poslist_good[mindex], np.min(fwhmlist_good))

            telescope.logger.info('checking if parabola is well-sampled')

            left = len(np.where( poslist_good < best_measured_focus[0] )[0])
            right = len(np.where( poslist_good > best_measured_focus[0] )[0])

            if left < 2:
                queue = np.append(queue, np.nanmin(pos_list) - stepsize)
                telescope.logger.info('adding additional autofocus step at {:.0f} mm'.format(np.nanmin(pos_list) - stepsize))

            if right < 2: 
                queue = np.append(queue, np.nanmax(pos_list) + stepsize)
                telescope.logger.info('adding additional autofocus step at {:.0f} mm'.format(np.nanmax(pos_list) + stepsize))

            if len(queue) > 0:
                continue

            if test:
                print('see if something is going wrong with fitting')
                ipdb.set_trace()

            telescope.logger.info('fitting quadratic')
            pos_bestfit, fwhm_bestfit = af_utils.do_quadfit(telescope, poslist_good, fwhmlist_good)
            
            if np.isnan(pos_bestfit):
                side = np.argmin([left, right])
                dxn = [-1, 1][side]
                queue = np.append(queue, [np.nanmin(pos_list), np.nanmax(fwhm_list)][side] + dxn * stepsize)
            else:
                break

#            pts_to_left = len(np.where( good_pos <  best_pos )[0])
#            pts_to_right = len(np.where( good_pos >  best_pos )[0])

#            if pts_to_left < 2 or good_fwhm[np.argmin(good_pos)] - np.min(good_fwhm) < 1:

#                queue = np.append(queue, np.min(pos_list) - stepsize)

#            if pts_to_right < 2 or good_fwhm[np.argmax(good_pos)] - np.min(good_fwhm) < 1:
                
#                queue = np.append(queue, np.max(pos_list) + stepsize)

#===================================================================================
# END OF AUTOFOCUS LOOP
#===================================================================================
            
        # fit succeeded; use best fitted focus
        if not np.isnan(pos_bestfit):
            best_focus = pos_bestfit
        
        # fit failed;
        else:
            best_measured_fwhm = np.min(good_fwhm)
            best_measured_pos = good_pos[np.argmin(good_fwhm)]
            
            # if the FWHM of our best step is less than 3'', use that position
            if best_measured_fwhm < 3.0:
                best_focus = best_measured_pos                
                telescope.logger.warning('Autofocus failed, using best measured focus ('\
                                         + str(best_measured_pos) + ',' + str(best_measured_fwhm) + ')')
            # if our best step is still bad, use the focus guess
            else:
                best_focus = focus_guess
                telescope.logger.warning('Autofocus failed, and best measured focus is bad ('\
                                          + str(best_measured_fwhm) + '"); using initial focus guess')

        # set focus!
        telescope.focus[m3port] = best_focus

        if test:
            ipdb.set_trace()
        
        # write the focus position to a text file
        filename = 'focus.' + telescope.logger_name + '.port' + m3port+'.txt'
        with open(filename, 'w') as f:
            f.write(str(telescope.focus[m3port]))

        # move to the focus position
        if not telescope.focuserMoveAndWait(telescope.focus[m3port], m3port):
            telescope.recoverFocuser(telescope.focus[m3port], m3port)
            telescope.acquireTarget(af_target)
        
        status = telescope.getStatus()
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

        try: # write autofocus record data to text file
            if len(imnum_list)==len(pos_list)==len(fwhm_list):
                ar_filename = '{}.{}.autorecord.port{}.{}.{}.{}.txt'.format(control.site.night, telid, m3port,\
                                                                            af_target['filter'][0], imnum_list[0],\
                                                                            imnum_list[-1])

                autodata = np.array([imnum_list, pos_list, fwhm_list]).T

                tel_header = '# Guess\tNew\tTM1\tTM2\tTM3\tTamb\tTback\talt\trotang\n'
                tel_info = '{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(focus_guess, telescope.focus[m3port], tm1, tm2, tm3,\
                                                                         tamb, tback, float(alt), rotang)
                # with open(ar_filename, 'a') as fd:
                #     fd.write(tel_header)
                #     fd.write(tel_info)
                #     fd.write(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')+'\n')

                data_header = 'Column 1\tImage number\n'+\
                              'Column 2\tFocuser position\n'+\
                              'Column 3\tMedian focus measure'
                header = tel_header + tel_info + data_header

                np.savetxt(datapath + ar_filename, autodata, fmt='%s', header=header)
            else:
                control.logger.error('mismatch length in autofocus arrays')
        except:
            control.logger.exception('unhandled error in autofocus results.')

        telescope.logger.info('Updating best focus for port '+str(m3port)+\
                                ' to '+ str(telescope.focus[m3port]))
        telescope.logger.info('Finished autofocus')
