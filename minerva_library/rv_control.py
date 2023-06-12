
import matplotlib
matplotlib.use('Agg',warn=False)
import threading
import control
import mail
import ipdb
import datetime
import sys, os, glob
import ephem
import targetlist
import env
import time
import utils
import numpy as np
import math
#import newauto
from autofocus import autofocus
from propagatingthread import PropagatingThread

def rv_observing(minerva):

    # python bug work around -- strptime not thread safe. Must call this once before starting threads    
    junk = datetime.datetime.strptime('2000-01-01 00:00:00','%Y-%m-%d %H:%M:%S')

    mail.send("MINERVA starting observing","Love,\nMINERVA")

    for dome in minerva.domes:
        sunfile = minerva.base_directory + 'minerva_library/sunOverride.' + dome.id + '.txt'
        if os.path.exists(sunfile): os.remove(sunfile)
        with open(minerva.base_directory + '/minerva_library/' + dome.id + '.request.txt','w') as fh:
            fh.write(str(datetime.datetime.utcnow()))

    minerva.telescope_initialize(tracking=False,derotate=False)
    minerva.telescope_park()

    # turn off both monitors
    minerva.logger.info('Turning off monitors')
    try: minerva.pdus[0].monitor.off()
    except: minerva.logger.exception("Turning off monitor in aqawan 1 failed")
    try: minerva.pdus[2].monitor.off()
    except: minerva.logger.exception("Turning off monitor in aqawan 2 failed")

    # if before the end of twilight, do calibrations
    if datetime.datetime.utcnow() < minerva.site.NautTwilEnd():
        backlight(minerva)
        minerva.specCalib()

    with open(minerva.base_directory + '/schedule/' + minerva.site.night + '.kiwispec.txt', 'r') as targetfile:
        for line in targetfile:
            target = minerva.parseTarget(line)
            print target
            if target <> -1:
                # truncate to now
                target = utils.truncate_observable_window(minerva.site, target, logger=minerva.logger)

                if target['starttime'] < target['endtime']:

                    if target['starttime'] > datetime.datetime.utcnow():
                        minerva.logger.info("waiting for start time (" + str(target['starttime']) + ')')
                        time.sleep((datetime.datetime.utcnow() - target['starttime']).total_seconds())

                    if target['name'] == 'autofocus':
                        if 'spectroscopy' in target.keys(): fau = target['spectroscopy']
                        else: fau = False
                        kwargs = {'target':target,'fau':fau}
                        threads = []
                        for telescope in minerva.telescopes:
                            thread = PropagatingThread(target=autofocus, args=(minerva,telescope.id,), kwargs=kwargs)
                            thread.name = str(telescope.id) + ' (rv_control->rv_observing->autofocus)'
                            threads.append(thread)
                        for thread in threads(): thread.start()
                        for thread in threads(): thread.join()
                    else:
                        telelist = []
                        for telescope in minerva.telescopes:
                            telelist.append(telescope.id)
                        doSpectra(minerva,target,telelist)
                else: minerva.logger.info(target['name']+ ' not observable; skipping')


    # all done; close the domes
    path = minerva.base_directory + '/minerva_library/'
    if os.path.exists(path + 'aqawan1.request.txt'): os.remove(path + 'aqawan1.request.txt')
    if os.path.exists(path + 'aqawan2.request.txt'): os.remove(path + 'aqawan2.request.txt')

    minerva.endNight()
    

def doSpectra(minerva, target, tele_list, simulate=False):

    # if after end time, return
    if datetime.datetime.utcnow() > target['endtime']:
        minerva.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + "); skipping")
        return

    # if before start time, wait
    if datetime.datetime.utcnow() < target['starttime']:
        waittime = (target['starttime']-datetime.datetime.utcnow()).total_seconds()
        minerva.logger.info("Target " + target['name'] + " is before its starttime (" + str(target['starttime']) + "); waiting " + str(waittime) + " seconds")
        time.sleep(waittime)

    if not simulate:
        # if the dome isn't open, wait for it to open
        for dome in minerva.domes:
            while not dome.isOpen():
                minerva.logger.info("Waiting for dome to open or until the target's end time (" + str(target['endtime']) + ')')
                if datetime.datetime.utcnow() > target['endtime']: 
                    minerva.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + ") while waiting for the dome to open; skipping")
                    return
                time.sleep(60)

    # acquire the target for each telescope
    threads = []
    for telid in tele_list:
        telescope = utils.getTelescope(minerva,telid)
        m3port = telescope.port['FAU']
        
        # JDE 2018-10-02: Don't do this (reduce mechanism wear, star not bright enough not to matter) 
        # block light from the star by switching to the imaging port (don't confuse star with fiber)
        #m3port = telescope.port['IMAGER'] 

        kwargs = {'tracking':True, 'derotate':False, 'm3port':m3port}
        minerva.logger.info("Starting acquisition for " + telid)
        thread = PropagatingThread(target = telescope.acquireTarget,args=(target,),kwargs=kwargs)
        thread.name = telescope.id + ' (rv_control->doSpectra->acquireTarget)'
        thread.start()
        threads.append(thread)

#        telescope.acquireTarget(target,tracking=True,derotate=False,m3port=m3port)

    minerva.logger.info("got here")

    # wait for all telescopes to get to the target
    # TODO: some telescopes could get in trouble and drag down the rest; keep an eye out for that
    t0 = datetime.datetime.utcnow()
    slewTimeout = 600.0 # sometimes it needs to home as part of a recovery, give it time for that
    for thread in threads:
        elapsedTime = (datetime.datetime.utcnow()-t0).total_seconds()
        minerva.logger.info("Waiting for all telescopes to slew (elapsed time = " + str(elapsedTime) + ")")
        thread.join(slewTimeout - elapsedTime)
        elapsedTime = (datetime.datetime.utcnow()-t0).total_seconds()

    # check if the thread timed out
    for t in range(len(tele_list)):
        if threads[t].isAlive():
            minerva.logger.error(tele_list[t] + " thread timed out waiting for slew")
            mail.send(tele_list[t] + " thread timed out waiting for slew",
                      "Dear Benevolent Humans,\n\n"+
                      tele_list[t] + " thread timed out waiting for slew. "+
                      "This shouldn't happen. Please fix me and note what was done."+
                      "Love,\nMINERVA",level='serious')
            # should kill the errant thread, otherwise all hell breaks loose

    max_obs_before_reacquire = 5

    # begin exposure(s)
    for i in range(target['num'][0]):

        minerva.logger.info('beginning exposure ' + str(i+1) + ' of ' + str(target['num'][0]))

        minerva.logger.info('checking max obs')
        if (i % max_obs_before_reacquire) == 0:

            if i > 0: 
                minerva.logger.info('Stopping guiding')
                stopFAU(minerva,tele_list)

            minerva.logger.info('done checking max obs')

            # take the backlit images
            minerva.logger.info("Locating Fiber")
            backlight(minerva)

            # find the fiber position from the backlit images
            for telid in tele_list:

                telescope = utils.getTelescope(minerva,telid)
                camera = utils.getCamera(minerva,telid)
        
                if 'backlight' not in camera.guider_file_name:
                    minerva.logger.error(telid + ": backlight image not taken; using default of (x,y) = (" + str(camera.fau.xfiber) + "," + str(camera.fau.yfiber) + ")")
                    mail.send(telid + " could not identify fiber position",
                              "Dear Benevolent Humans,\n\n"+
                              telid + " failed to take the backlight image and is relying on the default fiber position in the config file. This is likely to significantly impact throughput.\n\n" + 
                              "Love,\nMINERVA",level='serious')
                else:
                    xfiber, yfiber = find_fiber(telescope.datadir + minerva.night + '/' + camera.guider_file_name, camera, control=minerva)
                    if xfiber <> None:
                        minerva.logger.info(telid + ": Fiber located at (x,y) = (" + str(xfiber) + "," + str(yfiber) + ") in image " + camera.guider_file_name)
                        camera.fau.xfiber = xfiber
                        camera.fau.yfiber = yfiber
                    else:
                        minerva.logger.error(telid + ": failed to find fiber in image " + camera.guider_file_name + "; using default of (x,y) = (" + str(camera.fau.xfiber) + "," + str(camera.fau.yfiber) + ")")
                        mail.send(telid + " could not identify fiber position",
                                  "Dear Benevolent Humans,\n\n"+
                                  telid + " failed to idenitfy the fiber position and is relying on the default fiber position in the config file. This is likely to significantly impact throughput.\n\n" + 
                                  "Love,\nMINERVA",level='serious')

                camera.fau.guiding=True

            # switch all ports back to the FAU asynchronously
            minerva.m3port_switch_list('FAU',tele_list)
    
            # acquire the target, run autofocus, then start guiding
            minerva.logger.info("Beginning acquisition, autofocus, and guiding")
            threads = []
            for telid in tele_list:
                telescope = utils.getTelescope(minerva,telid)

                # set the timeout to be the end of exposure
                timeout = max([target['exptime'],300])
                kwargs = {'timeout':timeout, 'simulate':simulate}
                thread = PropagatingThread(target=acquireFocusGuide,args=(minerva,target,telid,),kwargs=kwargs)
                thread.name = telid + ' (rv_control->doSpectra->acquireFocusGuide)'
                thread.start()
                threads.append(thread)
        
            # wait for all telescopes to put target on their fibers (or timeout)
            # needs time to reslew (because m3port_switch stops tracking), fine acquire, autofocus, guiding
            nacquired = 0
            timeout = 750.0 
            elapsedTime = 0.0
            t0 = datetime.datetime.utcnow()
            while nacquired != len(tele_list) and elapsedTime < timeout:
                nacquired = 0
                for telid in tele_list:
                    camera = utils.getCamera(minerva,telid)
                    minerva.logger.info(telid + ": acquired = " + str(camera.fau.acquired))
                    if camera.fau.acquired: nacquired += 1
                    minerva.logger.info(telid + ": nacquired = " + str(nacquired))
                    if not camera.fau.acquired:
                        minerva.logger.info(telid + " has not acquired the target yet; waiting (elapsed time = " + str(elapsedTime) + ")")
                time.sleep(1.0)
                elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()

            # if none acquired the target, give up
            # otherwise, continue with what we have
            if nacquired == 0:
                minerva.logger.error("No telescopes acquired the target within the timeout; giving up. (clouds?)")
                stopFAU(minerva,tele_list)
                return

        # make sure we're not past the end time
        if datetime.datetime.utcnow() > (target['endtime']-datetime.timedelta(seconds=target['exptime'][0])):
            minerva.logger.info("target past its end time (" + str(target['endtime']) + '); skipping')
            stopFAU(minerva,tele_list)
            return

        # if the dome isn't open, wait for it to open (why is this here? -- how would we have acquired?)
        if not simulate:
            for dome in minerva.domes:
                if not dome.isOpen():
                    minerva.logger.info("Dome closed during sequence, aborting target " + target['name'])
                    stopFAU(minerva,tele_list)
                    return
                 
                # JDE: changed 2021-11-29 to prevent thread clashing in bad weather. hopefully.
                #while not dome.isOpen():
                #    minerva.logger.info("Waiting for dome to open")
                #    if datetime.datetime.utcnow() > (target['endtime']-datetime.timedelta(seconds=target['exptime'][0])):
                #        minerva.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + ") while waiting for the dome to open; skipping")
                #        stopFAU(minerva,tele_list)
                #        return
                #    time.sleep(60)

        minerva.logger.info('taking spectrum')
        minerva.takeSpectrum(target)
        minerva.logger.info('done taking spectrum')
        
    stopFAU(minerva,tele_list)

    # make sure all threads are done
    exposureTimeout = target['exptime'][0] + 600.0
    for t in range(len(tele_list)):
        telescope = utils.getTelescope(minerva,tele_list[t])
        telescope.abort=True
        elapsedTime = (datetime.datetime.utcnow()-t0).total_seconds()
        threads[t].join(30.0)#exposureTimeout - elapsedTime)
        telescope.abort=False

    # check if the thread timed out          
    for t in range(len(tele_list)):
        if threads[t].isAlive():
            minerva.logger.error(tele_list[t] + ": thread timed out while exposing")
            mail.send(tele_list[t] + " thread timed out waiting for slew",
                      "Dear Benevolent Humans,\n\n"+
                      tele_list[t] + " thread timed out while exposing. "+
                      "This shouldn't happen and will cause conflicts between "+
                      "threads. Please fix me and note what was done.\n\n"+
                      "Love,\nMINERVA",level='serious')
            # should kill the errant thread, otherwise all hell breaks loose                                                                                                        
    # let's take another backlit image to see how stable it was
    backlight(minerva)
    
    # stop tracking for all scopes (so they don't track out of bounds)
    for telescope in minerva.telescopes:
        telescope.mountTrackingOff()

    return

def acquireFocusGuide(minerva, target, telid, timeout=300.0, simulate=False):
    telescope = utils.getTelescope(minerva,telid)
    camera = utils.getCamera(minerva,telid)
    camera.fau.guiding=True
    t0 = datetime.datetime.utcnow()

    try:

#        # slew to the target
#        minerva.logger.info("beginning course acquisition")
#        telescope.acquireTarget(target,tracking=True,derotate=False,m3port=telescope.port['FAU'])
#        if (datetime.datetime.utcnow() - t0).total_seconds() > timeout or telescope.abort:
#            minerva.logger.error("course acquisition timed out")
#            return

        # autofocus
        minerva.logger.info("beginning autofocus")
        try: autofocus(minerva, telid, simulate=simulate, slew=False, target=target, exptime=target['fauexptime'])
        except: minerva.logger.exception("autofocus failed")
        if (datetime.datetime.utcnow() - t0).total_seconds() > timeout or telescope.abort:
            minerva.logger.error("autofocus timed out")
            return

        if telescope.abort:
            minerva.logger.error("aborted by telescope; returning")
            return

        # if there's a focus offset (FAU and Fiber have a calibrated offset), apply it
        if camera.fau.focusOffset != 0 and not telescope.abort:
            m3port = telescope.port['FAU']
            try: 
                minerva.logger.info("focus offset of " + str(camera.fau.focusOffset) + " being applied")
                telescope.focuserMoveAndWait(telescope.focus[m3port]+camera.fau.focusOffset, m3port)
            except: minerva.logger.exception("focusing failed")

#        # put the target on the fiber
#        minerva.logger.info("beginning fine acquisition")
#        try: minerva.fauguide(target,telid,acquireonly=True, skiponfail=True, simulate=simulate)
#        except: minerva.logger.exception("acquisition failed")
#        if (datetime.datetime.utcnow() - t0).total_seconds() > timeout or telescope.abort:
#            minerva.logger.error("fine acquisition timed out")
#            return

        # put the target on the fiber and start guiding
        minerva.logger.info("beginning fine acquistion and guiding")
        try: minerva.fauguide(target,telid, skiponfail=True, simulate=simulate)
        except: minerva.logger.exception("guiding failed")
        if (datetime.datetime.utcnow() - t0).total_seconds() > timeout or telescope.abort:
            if not telescope.abort:
                minerva.logger.error("guiding timed out")
            return

    except:
        minerva.logger.exception("pointing and guiding failed")
        mail.send("Pointing and guiding failed","",level="serious")

def stopFAU(minerva,tele_list):
    # set camera.fau.guiding == False to stop guiders
    minerva.logger.info("Stopping the guiding loop for all telescopes")
    for telid in tele_list:
        camera = utils.getCamera(minerva,telid)
        camera.fau.guiding = False
    minerva.logger.info("Waiting 60 seconds for guiders to stop. Please revisit for efficiency")
    time.sleep(60)
    

def peakupflux(minerva, target, telid):

#    minerva.fauguide(target,[telid], xfiber=camera.fau.xfiber, yfiber=camera.fau.yfiber)
#    aveflux = 

    pass


def endNight(minerva):

    for telescope in minerva.telescopes:
        minerva.endNight(num=int(telescope.num), email=False)
    minerva.endNight(kiwispec=True)

def backlight(minerva, tele_list=0, exptime=0.01, name='backlight'):

    if exptime == 0.01 and minerva.red:
        exptime = 2.0

    #S check if tele_list is only an int
    if type(tele_list) is int:
        #S Catch to default a zero argument or outside array range tele_list 
        #S and if so make it default to controling all telescopes.
        if (tele_list < 1) or (tele_list > len(minerva.telescopes)):
            tele_list = []
            for telescope in minerva.telescopes:
                tele_list.append(telescope.id)
        #S If it is in the range of telescopes, we'll put in a list to
        # avoid issues later on
        else:
            tele_list = [tele_list]

    minerva.logger.info("Doing backlit images for telescopes " + ",".join([str(x) for x in tele_list]))

    # Turn off the expmeter (high voltage, close shutter). this waits for a response that 
    # the high voltage supply has been turned off (in a weird way, look in spec_server)
#    minerva.spectrograph.stop_log_expmeter()

    # swap to the imaging port to block light from the telescope
#    minerva.m3port_switch_list('IMAGER',tele_list)

    # turn on the backlight LED and move the motor to cover the input optics
    minerva.logger.info("Turning on the backlight")
    response = minerva.spectrograph.backlight_on()
    if response == 'fail': 
        minerva.logger.error("Turning on the backlight failed")

    t0 = datetime.datetime.utcnow()

#    # wait for the LED to warm up
#    elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
#    warmuptime = 2.0
#    if elapsedTime < warmuptime:
#        time.sleep(warmuptime - elapsedTime)

    # take images with all FAUs
    fau_threads = []
    for telid in tele_list:
        telescope = utils.getTelescope(minerva, telid)
        target = {
            'name':name,
            'fauexptime':exptime,
            }
        thread = PropagatingThread(target=minerva.takeFauImage,args=[target,telescope.id],)
        thread.name = telescope.id + ' (rv_control->backlight->takeFauImage)'
        fau_threads.append(thread)

    # start all the FAU images
    for fau_thread in fau_threads:
        fau_thread.start()

    # wait for all fau images to complete
    for fau_thread in fau_threads:
        fau_thread.join(300)

    # turn off the backlight LEDs
    minerva.spectrograph.backlight_off()
    minerva.logger.info("Done with backlit images")

    # open expmeter shutter
#    minerva.spectrograph.start_log_expmeter()

# given a backlit FAU image, locate the fiber
def find_fiber(imagename, camera, tolerance=10.0,control=None):
    
    catname = utils.sextract('',imagename,sexfile='backlight.sex')
    cat = utils.readsexcat(catname)

    # find the brightest thing within TOLERANCE of the fiber
    try:
        xpos = cat['XWIN_IMAGE']
        ypos = cat['YWIN_IMAGE']
        alldist = np.sqrt(np.power(camera.fau.xfiber - xpos,2) + np.power(camera.fau.yfiber-ypos,2))
        good = np.where(alldist <= tolerance)
    except:
        camera.logger.error("Error reading image " + imagename)
        return None, None

    if len(good[0]) < 1:
        camera.logger.warning("No sources found within " + str(tolerance) + " of expected position")
        return None, None

    # readsexcat will return an empty dictionary if it fails
    # and a dictionary with empty lists if there are no targets
    # both will be caught (and missing key) by this try/except
    try: brightest = np.argmax(cat['FLUX_ISO'][good])
    except: 
        camera.logger.warning("error finding brighest star")
        return None, None


    try:
        xfiber = xpos[good[brightest]][0]
        yfiber = ypos[good[brightest]][0]
        dist = alldist[good[brightest]][0]
        if dist <= tolerance:
            camera.logger.info("Fiber found at (" + str(xfiber) +","+str(yfiber) + "), "+ str(dist) + " pixels from nominal position")
            
            #S if a control class is handed to find_fiber
            if control!=None:
                #S get the zero-indexed telescope number
                telescope = utils.getTelescope(control,camera.telid)

                #S get the status of the telescope the camera is on
                status = telescope.getStatus()
                focuserStatus = telescope.getFocuserStatus(telescope.port['FAU'])
                rotatorStatus = telescope.getRotatorStatus(telescope.port['FAU'])
                try: alt = '%.3f'%(np.degrees(float(status.mount.alt_radian)))
                except: alt = 'UNKNOWN'
                try: azm = '%.3f'%np.degrees(float(status.mount.azm_radian)) 
                except: azm = 'UNKNOWN'
                try: focpos = str(focuserStatus.position)
                except: focpos = 'UNKNOWN'
                try: rotpos = str(rotatorStatus.position)
                except: rotpos = 'UNKNOWN'
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
            
                camera.logger.info(('fibstab001, Fiberpos:(%0.3f,%0.3f), '+\
                                        'dist:%0.3f, T:%s, alt:%s, azm:%s, '+\
                                        'focpos:%s, rotpos:%s, tm1:%s, '+\
                                        'tm2:%s, tm3:%s, tamb:%s, tback:%s'),\
                                       xfiber,yfiber,dist,telescope.id,alt,azm,\
                                       focpos,rotpos,tm1,tm2,tm3,tamb,tback)

                
            
            return xfiber, yfiber
        else:
            camera.logger.info("Object found at (" + str(xfiber) +","+str(yfiber) + "), but "+ str(dist) + " is greater than fiber tolerance")
    except:
        camera.logger.exception("Error finding fiber position")

    camera.logger.error("error finding fiber position 2")
    return None, None

def rv_observing_catch(minerva):
    try:
        rv_observing(minerva)
    except Exception as e:
        minerva.logger.exception('rv_observing thread died: ' + str(e.message) )
        body = "Dear benevolent humans,\n\n" + \
            'I have encountered an unhandled exception which has killed the rv_observing control thread at ' + str(datetime.datetime.utcnow()) + '. The error message is:\n\n' + \
            str(e.message) + "\n\n" + \
            "Check control.log for additional information. Please investigate, consider adding additional error handling, and restart 'main.py\n\n'" + \
            "Love,\n" + \
            "MINERVA"
        mail.send("rv_observing thread died",body,level='serious')
        sys.exit()

def fiber_stability(minerva):

    timeout = 360.0

    '''
    # evaluate stability as a function of alt/az/rotation
    for rotang in range(0,360,10):

        threads = []
        for telescope in minerva.telescopes:
            m3port = telescope.port['FAU']
        
            thread = PropagatingThread(target=telescope.rotatorMove,args=[rotang,m3port])
            thread.name = telescope.id
            threads.append(thread)
        for thread in threads:
            thread.start()
    '''
   
    # now slew in alt/az
    for az in range(0,270,90):
        for alt in range(21,84,15):
            
            minerva.telescope_mountGotoAltAz(alt,az)
            
            t0 = datetime.datetime.utcnow()
            elapsedTime = 0.0

                # wait for telescopes to get in position
            for telescope in minerva.telescopes:
                while not telescope.inPosition(alt=alt,az=az,pointingTolerance=3600.0) and elapsedTime < timeout:
                    time.sleep(1)
                    elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
                
            backlight(minerva)
            # doesn't work if any telescope offline!
            for ind in np.arange(4):
                path = '/Data/t%s/%s/%s'\
                    %(str(ind+1),minerva.night,\
                          minerva.cameras[ind].guider_file_name)
                find_fiber(path, minerva.cameras[ind],control=minerva)
                
                

def get_rv_target(minerva, bstar=False):
    targets = targetlist.mkdict(bstar=bstar)

    # use astronomical twilight
    sunset = minerva.site.sunset(horizon=-18)
    sunrise = minerva.site.sunrise(horizon=-18)

    goodtargets = []
    for target in targets:

        utils.truncate_observable_window(minerva.site, target)

        if target['starttime'] < target['endtime']:
            goodtargets.append(target)

    for target in goodtargets:
        print target['name'] + ' ' + str(target['starttime']) + ' ' + str(target['endtime'])

    return goodtargets
        
def mkschedule(minerva):
    night = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime('n%Y%m%d')
    scheduleFile = minerva.base_directory + '/schedule/' + night + '.kiwispec.txt' 

    
    print scheduleFile
    sunset = minerva.site.sunset(horizon=-18)
    sunrise = minerva.site.sunrise(horizon=-18)

    num = 1
    bnum = 1
    
    targets = get_rv_target(minerva)
    bstars = get_rv_target(minerva,bstar=True)

    for target in targets:
        target['num'] = [num]
    for bstar in bstars:
        bstar['num'] = [bnum]

    acquisitionOverhead = 300.0
    readTime = 21.7
    elapsedTime = 0.0

    print ((sunrise-sunset).total_seconds() + 3600.0)/3600.0

    print scheduleFile
    fh = open(scheduleFile,'w')

    # add a B star to the beginning of the night
    added = False
    for bstar in bstars:
        acquisitionTime = (acquisitionOverhead + bnum*(readTime+bstar['exptime'][0]))
        starttime = sunset + datetime.timedelta(seconds=elapsedTime)
        endtime = sunset + datetime.timedelta(seconds=elapsedTime+acquisitionTime)
        print starttime, endtime, bstar['starttime'], bstar['endtime']
        if (endtime <= bstar['endtime'] and starttime >= bstar['starttime']) or (starttime >= bstar['starttime'] and bstar['endtime'] == sunrise) and not added:
            bstar['expectedStart'] = str(sunset + datetime.timedelta(seconds=elapsedTime))
            bstar['expectedEnd'] = str(sunset + datetime.timedelta(seconds=elapsedTime + acquisitionTime))
                
            elapsedTime += acquisitionTime

            jsonstr = targetlist.target2json(bstar)
            fh.write(jsonstr + '\n')
            added = True
            print "added " +bstar['name']
            break

    while ((sunrise-sunset).total_seconds() + 3600.0) > elapsedTime:

        for target in targets:
            acquisitionTime = acquisitionOverhead + num*(readTime+target['exptime'][0])

            starttime = sunset + datetime.timedelta(seconds=elapsedTime)
            endtime = sunset + datetime.timedelta(seconds=elapsedTime+acquisitionTime)
            if (endtime <= target['endtime'] and starttime >= target['starttime']) or (starttime >= target['starttime'] and target['endtime'] == sunrise):

                target['expectedStart'] = str(sunset + datetime.timedelta(seconds=elapsedTime))
                target['expectedEnd'] = str(sunset + datetime.timedelta(seconds=elapsedTime + acquisitionTime))

# # *** DONT LEAVE THIS IN HERE, ONLY MAKING TEMPLATES FOR TESTING **** 
#                target['template'] = True
#                target['i2'] = False
# # *** DONT LEAVE THIS IN HERE **** 

                # add a target to the schedule
                elapsedTime += acquisitionTime
                jsonstr = targetlist.target2json(target)
                fh.write(jsonstr + '\n')

            if ((sunrise-sunset).total_seconds() + 3600.0) < elapsedTime:
                break
        if elapsedTime == 0:
            print "no targets at sunset"
            break

    print scheduleFile
    fh.close()



if __name__ == "__main__":

    minerva = control.control('control.ini','/home/minerva/minerva-control')

#    endNight(minerva)
#    sys.exit()
    mkschedule(minerva)
    sys.exit()
    
     
    minerva.telescope_initialize(tracking=False,derotate=False)
    minerva.telescope_park()


#    ipdb.set_trace()
    fiber_stability(minerva)

#    # figure out the optimal stage position for i2 stage during backlighting (81 mm)
#    for i in range(20):
#        backlight(minerva,stagepos=73.0 + float(i), name='backlight' + str(int(73.0 + float(i))))



                



