### ===========================================================================
### Written by Cayla Dedrick as a replacement for newauto.py
### Significant code stolen from newauto.py
### Last updated 2021-02-14
### ===========================================================================

import numpy as np
import matplotlib.pyplot as plt
import subprocess
import warnings
import datetime
import time
import copy
import glob

import utils
import af_utils

def autofocus(control, telid, num_steps = 3, defocus_step = 0.3,
              target = None, exptime = 15.0, dome_override = False,
              slew = True, simulate = False):
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
            return False

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

        # start with 3 steps centered at best focus guess
        # add first 3 steps to step queue
        init_steps = focus_guess + (np.linspace(-1, 1, 3) * stepsize)

        pos_list = np.array([])
        fwhm_list = np.array([])
        imnum_list = np.array([])
        
        std_list = np.array([])
        n_list = np.array([])

        queue = init_steps
        pos_bestfit = np.nan

        while len(pos_list) < 15:             # if routine hasn't worked after 15 steps (CD: changed from 10 steps on 2021-01-06), give up
            while len(queue) > 0:              # loop through steps in queue 
                # first, check if abort == True
                if telescope.abort:
                    telescope.logger.info("Autofocus aborted")
                    return

                focuserStatus = telescope.getFocuserStatus(m3port)
                focuser_pos = int(focuserStatus.position)

                # start with step closest to the current position of the focuser
                goto = np.argmin(np.abs(focuser_pos - queue))
                new_focuser_pos = queue[goto]
                telescope.logger.info("New step is " + str(new_focuser_pos))

                median, std, numstars, imnum = af_utils.autofocus_step(control, telescope, new_focuser_pos, af_target)

                pos_list = np.append(pos_list, new_focuser_pos)
                fwhm_list = np.append(fwhm_list, median * platescale)
                imnum_list = np.append(imnum_list, str(imnum))
                # for photometry, i guess
                std_list = np.append(std_list,std)
                n_list = np.append(n_list,numstars)

                queue = np.delete(queue, goto)

            # get the indices of the non-nan points
            goodind = np.where(np.logical_not(np.isnan(fwhm_list)))[0]

            # if no stars are found in the first pass through, give up
            if len(pos_list) >= 5 and len(goodind) == 0:
                telescope.logger.error('No stars in first five autofocus images; autofocus failed')
                break

            good_pos = pos_list[goodind]
            good_fwhm = fwhm_list[goodind]

            min_dex = np.argmin(good_fwhm)
            pos_bestmeas = good_pos[min_dex]
            fwhm_bestmeas = np.min(good_fwhm)

            queue = np.array([])            
            
            # check that we have enough points to fit
            if len(goodind) <= 4:
                step = af_utils.queue_up(good_pos, good_fwhm, stepsize)
                telescope.logger.info('adding additional autofocus step at {:.0f} mm'.format(step)) 
                queue = np.append(queue, step)
                continue
            
            # fit parabola
            pos_bestfit, fwhm_bestfit = af_utils.do_quadfit(telescope, good_pos, good_fwhm, logger=telescope.logger)    

            # check that fit worked and wasn't upside-down
            if np.isnan(pos_bestfit):
                step = af_utils.queue_up(good_pos, good_fwhm, stepsize)
                telescope.logger.info('adding additional autofocus step at {:.0f} mm'.format(step))
                queue = np.append(queue, step)
                continue

            # check that parabola isn't super one-sided
            telescope.logger.info('checking that parabola is well-sampled on both sides of the minimum')
            pts_to_left = len(np.where( good_pos <  pos_bestmeas )[0])
            telescope.logger.info('there are ' + str(pts_to_left) + ' below the minimum')
            pts_to_right = len(np.where( good_pos >  pos_bestmeas )[0])
            telescope.logger.info('there are ' + str(pts_to_right) + ' above the minimum')

            if pts_to_left <= 2 or pts_to_right <= 2:
                
                telescope.logger.info('parabola is not well-sampled, queuing up new  autofocus steps')
                step = af_utils.queue_up(good_pos, good_fwhm, stepsize, pos_bestfit)
                telescope.logger.info('adding additional autofocus step at {:.0f} mm'.format(step))
                queue = np.append(queue, step)
                continue

            if len(queue) == 0:
                telescope.logger.info('Autofocus fit is good!')
                break

            if len(pos_list) == 15:
                telescope.logger.warning('Autofocus was unable to determine the best focus after 15 steps, moving on.')

        # set the new focus 
        if not np.isnan(pos_bestfit):
            # fit succeeded; use best fitted focus
            telescope.logger.info('Fit succeeded; using the best fit focus')
            telescope.focus[m3port] = pos_bestfit
        else:
            # fit failed;
            best_measured_fwhm = np.nanmin(fwhm_list)
            best_measured_pos = pos_list[np.nanargmin(fwhm_list)]
            if best_measured_fwhm <= 3.0:
                # if the FWHM of our best step is less than 3'', use that position
                telescope.logger.warning('Autofocus failed, using best measured focus ('\
                                         + str(best_measured_pos) + ',' + str(best_measured_fwhm) + ')')
                telescope.focus[m3port] = best_measured_pos
            else:
                # if our best step is still bad, use the focus guess
                telescope.logger.warning('Autofocus failed, and best measured focus is bad ('\
                                          + str(best_measured_fwhm) + '"); using initial focus guess')

        # Save all the relevant info to text files:

        # write the focus position to a text file
        filename = 'focus.' + telescope.logger_name + '.port' + m3port+'.txt'
        with open(datapath + filename, 'w') as f:
            f.write(str(telescope.focus[m3port]))

        status = telescope.getStatus() 
        rotatorStatus = telescope.getRotatorStatus(m3port)

        # record values that may correlate with focus
        ## Mount Altitude
        try: alt = str(np.rad2deg(float(status.mount.alt_radian)))
        except: alt = '-1'
        ## Rotator Angle
        try: rotang = str(float(rotatorStatus.position))
        except: rotang = '720'
        ## Various Temperatures
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
            if len(imnum_list)==len(pos_list)==len(fwhm_list):
                ar_filename = '{}.{}.autorecord.port{}.{}.{}.{}.txt'.format(control.site.night, telid, m3port,\
                                                                            af_target['filter'][0], imnum_list[0],\
                                                                            imnum_list[-1])

                autodata = np.array([imnum_list, pos_list, fwhm_list]).T

                tel_header = '# Guess\tNew\tTM1\tTM2\tTM3\tTamb\tTback\talt\trotang\n'
                tel_info = '{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(focus_guess, telescope.focus[m3port], tm1, tm2, tm3,\
                                                                         tamb, tback, float(alt), rotang)
                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') +'\n'
 #               with open(ar_filename, 'a') as fd:
 #                   fd.write(tel_header)
 #                   fd.write(tel_info)
 #                   fd.write(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')+'\n')

                data_header = 'Column 1\tImage number\n'+\
                               'Column 2\tFocuser position\n'+\
                               'Column 3\tMedian focus measure'
                
                header = tel_header + tel_info + now + data_header

                np.savetxt(datapath + ar_filename, autodata, fmt='%s', header=header)

            else:
                control.logger.error('mismatch length in autofocus arrays')
        except:
            control.logger.exception('unhandled error in autofocus results.')
        
        # move to the new focus position
        if not telescope.focuserMoveAndWait(telescope.focus[m3port], m3port):
            telescope.recoverFocuser(telescope.focus[m3port], m3port)
            telescope.acquireTarget(af_target)

        telescope.logger.info('Updating best focus for port '+str(m3port)+                          ' to '+str(telescope.focus[m3port])+' (TM1='+tm1 +\
                        ', TM2=' + tm2 + ', TM3=' + tm3 + ', Tamb=' + \
                        tamb + ', Tback=' + tback + ', alt=' + alt + ')' )
        telescope.logger.info('Finished autofocus')

        if np.isnan(pos_bestfit):
            return False
        
        return True
        
