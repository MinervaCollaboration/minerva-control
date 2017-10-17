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
import newauto

def rv_observing(minerva):

    # python bug work around -- strptime not thread safe. Must call this once before starting threads    
    junk = datetime.datetime.strptime('2000-01-01 00:00:00','%Y-%m-%d %H:%M:%S')

    mail.send("MINERVA starting observing","Love,\nMINERVA")

    sunfile = minerva.base_directory + 'minerva_library/sunOverride.txt'
    if os.path.exists(sunfile): os.remove(sunfile)
    with open(minerva.base_directory + '/minerva_library/aqawan1.request.txt','w') as fh:
        fh.write(str(datetime.datetime.utcnow()))

    with open(minerva.base_directory + '/minerva_library/aqawan2.request.txt','w') as fh:
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
                # check if the end is after morning twilight begins
                if target['endtime'] > minerva.site.NautTwilBegin():
                    target['endtime'] = minerva.site.NautTwilBegin()

                # check if the start is after evening twilight ends
                if target['starttime'] < minerva.site.NautTwilEnd():
                    target['starttime'] = minerva.site.NautTwilEnd()

                # compute the rise/set times of the target
                #S I think something with coordinates is screwing us up here
                #S We are still going below 20 degrees.                
                minerva.site.obs.horizon = '25.0'
                body = ephem.FixedBody()
                body._ra = str(target['ra'])
                body._dec = str(target['dec'])
                    
                #S using UTC now for the epoch, shouldn't make a significant
                #S difference from using local time
                body._epoch = datetime.datetime.utcnow()
                body.compute()
                        
                try:
                    risetime = minerva.site.obs.next_rising(body,start=minerva.site.NautTwilEnd()).datetime()
                except ephem.AlwaysUpError:
                    # if it's always up, don't modify the start time
                    risetime = target['starttime']
                except ephem.NeverUpError:
                    # if it's never up, skip the target
                    risetime = target['endtime']
                try:
                    settime = minerva.site.obs.next_setting(body,start=minerva.site.NautTwilEnd()).datetime()
                except ephem.AlwaysUpError:
                    # if it's always up, don't modify the end time
                    settime = target['endtime']
                except ephem.NeverUpError:
                    # if it's never up, skip the target
                    settime = target['starttime']
                if risetime > settime:
                    try:
                        risetime = minerva.site.obs.next_rising(body,start=minerva.site.NautTwilEnd()-datetime.timedelta(days=1)).datetime()
                    except ephem.AlwaysUpError:
                        # if it's always up, don't modify the start time
                        risetime = target['starttime']
                    except ephem.NeverUpError:
                        # if it's never up, skip the target
                        risetime = target['endtime']

                # make sure the target is always above the horizon
                if target['starttime'] < risetime:
                    target['starttime'] = risetime
                if target['endtime'] > settime:
                    target['endtime'] = settime

                if target['starttime'] < target['endtime']:
                    if target['name'] == 'autofocus':
                        if 'spectroscopy' in target.keys(): fau = target['spectroscopy']
                        else: fau = False
                        kwargs = {'target':target,'fau':fau}
                        threads = []
                        for telescope in minerva.telescopes:
                            thread = threading.Thread(target=newauto.autofocus,args=(minerva,int(telescope.num),),kwargs=kwargs)
                            thread.name = 'T' + str(telescope.num)
                            threads.append(thread)
                        for thread in threads(): thread.start()
                        for thread in threads(): thread.join()
                    else:
                        doSpectra(minerva,target,[1,2,3,4])
                else: minerva.logger.info(target['name']+ ' not observable; skipping')


    # all done; close the domes
    path = minerva.base_directory + '/minerva_library/'
    if os.path.exists(path + 'aqawan1.request.txt'): os.remove(path + 'aqawan1.request.txt')
    if os.path.exists(path + 'aqawan2.request.txt'): os.remove(path + 'aqawan2.request.txt')

    minerva.endNight()
    

def doSpectra(minerva, target, tele_list, test=False):

    # if after end time, return
    if datetime.datetime.utcnow() > target['endtime']:
        minerva.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + "); skipping")
        return

    # if before start time, wait
    if datetime.datetime.utcnow() < target['starttime']:
        waittime = (target['starttime']-datetime.datetime.utcnow()).total_seconds()
        minerva.logger.info("Target " + target['name'] + " is before its starttime (" + str(target['starttime']) + "); waiting " + str(waittime) + " seconds")
        time.sleep(waittime)

    if not test:
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
#        m3port = telescope.port['IMAGER'] # why was this the imager JDE 2016-12-18??
        kwargs = {'tracking':True, 'derotate':False, 'm3port':m3port}
        thread = threading.Thread(target = telescope.acquireTarget,args=(target,),kwargs=kwargs)
        thread.name = telescope.id
        thread.start()
        threads.append(thread)

    # wait for all telescopes to get to the target
    # TODO: some telescopes could get in trouble and drag down the rest; keep an eye out for that
    minerva.logger.info("Waiting for all telescopes to slew")
    t0 = datetime.datetime.utcnow()
    slewTimeout = 660.0 # sometimes it needs to home as part of a recovery, give it time for that
    for thread in threads:
        elapsedTime = (datetime.datetime.utcnow()-t0).total_seconds()
        thread.join(slewTimeout - elapsedTime)

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

    # take the backlit images
    minerva.logger.info("Locating Fiber")
    backlight(minerva)

    # find the fiber position from the backlit images
    for telid in tele_list:

        telescope = utils.getTelescope(minerva,telid)
        camera = utils.getCamera(minerva,telid)
        
        if 'backlight' not in camera.file_name:
            minerva.logger.error(telid + ": backlight image not taken; using default of (x,y) = (" + str(camera.fau.xfiber) + "," + str(camera.fau.yfiber) + ")")
        else:
            xfiber, yfiber = find_fiber(telescope.datadir + minerva.night + '/' + camera.file_name, camera)
            if xfiber <> None:
                minerva.logger.info(telid + ": Fiber located at (x,y) = (" + str(xfiber) + "," + str(yfiber) + ") in image " + camera.file_name)
                camera.fau.xfiber = xfiber
                camera.fau.yfiber = yfiber
            else:
                minerva.logger.error(telid + ": failed to find fiber in image " + camera.file_name + "; using default of (x,y) = (" + str(camera.fau.xfiber) + "," + str(camera.fau.yfiber) + ")")

        camera.fau.guiding=True

    # switch all ports back to the FAU asynchronously
    minerva.m3port_switch_list('FAU',tele_list)
    
    # acquire the target, run autofocus, then start guiding
    minerva.logger.info("Beginning fine acquisition, autofocus, and guiding")
    threads = []
    for telid in tele_list:
        telescope = utils.getTelescope(minerva,telid)
        thread = threading.Thread(target=acquireFocusGuide,args=(minerva,target,telid,))
        thread.name = telid
        thread.start()
        threads.append(thread)
        
    # wait for all telescopes to put target on their fibers (or timeout)
    # needs time to reslew (because m3port_switch stops tracking), fine acquire, autofocus, guiding
    acquired = False
    timeout = 300.0 
    elapsedTime = 0.0
    t0 = datetime.datetime.utcnow()
    while not acquired and elapsedTime < timeout:
        acquired = True
        for i in range(len(tele_list)):
            camera = utils.getCamera(minerva,tele_list[i])
            minerva.logger.info(tele_list[i] + ": acquired = " + str(camera.fau.acquired))
            if not camera.fau.acquired:
                minerva.logger.info(tele_list[i] + " has not acquired the target yet; waiting (elapsed time = " + str(elapsedTime) + ")")
                acquired = False
        time.sleep(1.0)
        elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()

    # what's the right thing to do in a timeout?
    # Try again?
    # Go on anyway? (as long as one telescope succeeded?)
    # We'll try going on anyway for now...
        
    # begin exposure(s)
    for i in range(target['num'][0]):
        # make sure we're not past the end time
        if datetime.datetime.utcnow() > target['endtime']:
            minerva.logger.info("target past its end time (" + str(target['endtime']) + '); skipping')
            stopFAU(minerva,tele_list)
            return

        # if the dome isn't open, wait for it to open
        for dome in minerva.domes:
            while not dome.isOpen():
                minerva.logger.info("Waiting for dome to open")
                if datetime.datetime.utcnow() > target['endtime']: 
                    minerva.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + ") while waiting for the dome to open; skipping")
                    stopFAU(minerva,tele_list)
                    return
                time.sleep(60)

        minerva.takeSpectrum(target)
        
    stopFAU(minerva,tele_list)

    # let's take another backlit image to see how stable it was
    backlight(minerva)

    return

def acquireFocusGuide(minerva, target, telid):
    telescope = utils.getTelescope(minerva,telid)
    camera = utils.getCamera(minerva,telid)
    camera.fau.guiding=True

    try:
        # slew to the target
        minerva.logger.info("beginning course acquisition")
        telescope.acquireTarget(target,tracking=True,derotate=False,m3port=telescope.port['FAU'])
        
        # put the target on the fiber
        minerva.logger.info("beginning fine acquisition")
        try: minerva.fauguide(target,telid,acquireonly=True, skiponfail=True)
        except: minerva.logger.exception("acquisition failed")

        # autofocus
        minerva.logger.info("beginning autofocus")
        try: newauto.autofocus(minerva, telid)
        except: minerva.logger.exception("autofocus failed")

        # guide
        minerva.logger.info("beginning guiding")
        try: minerva.fauguide(target,telid, skiponfail=True)
        except: minerva.logger.exception("guiding failed")
    except:
        minerva.logger.exception("pointing and guiding failed")
        #mail.send("Pointing and guiding failed","",level="serious")

def stopFAU(minerva,tele_list):
    # set camera.fau.guiding == False to stop guiders
    minerva.logger.info("Stopping the guiding loop for all telescopes")
    for telid in tele_list:
        camera = utils.getCamera(minerva,telid)
        camera.fau.guiding = False

def peakupflux(minerva, target, telid):

#    minerva.fauguide(target,[telid], xfiber=camera.fau.xfiber, yfiber=camera.fau.yfiber)
#    aveflux = 

    pass


def endNight(minerva):

    for telescope in minerva.telescopes:
        minerva.endNight(num=int(telescope.num), email=False)
    minerva.endNight(kiwispec=True)

def backlight(minerva, tele_list=0, exptime=0.03, name='backlight'):

    #S check if tele_list is only an int
    if type(tele_list) is int:
        #S Catch to default a zero argument or outside array range tele_list 
        #S and if so make it default to controling all telescopes.
        if (tele_list < 1) or (tele_list > len(minerva.telescopes)):
            #S This is a list of numbers fron 1 to the number scopes
            tele_list = [x+1 for x in range(len(minerva.telescopes))]
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
    minerva.spectrograph.backlight_on()
    t0 = datetime.datetime.utcnow()

#    # wait for the LED to warm up
#    elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
#    warmuptime = 2.0
#    if elapsedTime < warmuptime:
#        time.sleep(warmuptime - elapsedTime)

    # take images with all FAUs
    fau_threads = []
    for i in range(len(tele_list)):
        telescope = utils.getTelescope(minerva, tele_list[i])
        target = {
            'name':name,
            'fauexptime':exptime,
            }
        thread = threading.Thread(target=minerva.takeFauImage,args=[target,telescope.id],)
        thread.name = telescope.id
        fau_threads.append(thread)

    # start all the FAU images
    for fau_thread in fau_threads:
        fau_thread.start()

    # wait for all fau images to complete
    for fau_thread in fau_threads:
        fau_thread.join()

    # turn off the backlight LEDs
    minerva.spectrograph.backlight_off()
    minerva.logger.info("Done with backlit images")

    # open expmeter shutter
#    minerva.spectrograph.start_log_expmeter()

# given a backlit FAU image, locate the fiber
def find_fiber(imagename, camera, tolerance=5.,control=None):
    
    catname = utils.sextract('',imagename,sexfile='backlight.sex')
    cat = utils.readsexcat(catname)

    # readsexcat will return an empty dictionary if it fails
    # and a dictionary with empty lists if there are no targets
    # both will be caught (and missing key) by this try/except
    try: brightest = np.argmax(cat['FLUX_ISO'])
    except: return None, None

    try:
        xfiber = cat['XWIN_IMAGE'][brightest]
        yfiber = cat['YWIN_IMAGE'][brightest]        
        dist = math.sqrt(math.pow(camera.fau.xfiber - xfiber,2) + math.pow(camera.fau.yfiber-yfiber,2))
        if dist <= tolerance:
            if control==None:
                camera.logger.info("Fiber found at (" + str(xfiber) +","+str(yfiber) + "), "+ str(dist) + " pixels from nominal position")
            
            #S if a control class is handed to find_fiber
            elif control!=None:
                #S get the zero-indexed telescope number
                telescope = utils.getTelescope(control,camera.telescope)

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
                str_telnum = str(telnum + 1)
            
                camera.logger.info(('fibstab001, Fiberpos:(%0.3f,%0.3f), '+\
                                        'dist:%0.3f, T:%s, alt:%s, azm:%s, '+\
                                        'focpos:%s, rotpos:%s, tm1:%s, '+\
                                        'tm2:%s, tm3:%s, tamb:%s, tback:%s'),\
                                       xfiber,yfiber,dist,str_telnum,alt,azm,\
                                       focpos,rotpos,tm1,tm2,tm3,tamb,tback)

                
            
            return xfiber, yfiber
        else:
            camera.logger.info("Object found at (" + str(xfiber) +","+str(yfiber) + "), but "+ str(dist) + " is greater than fiber tolerance")
    except:
        camera.logger.exception("Error finding fiber position")

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
        
            thread = threading.Thread(target=telescope.rotatorMove,args=[rotang,m3port])
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
            for ind in np.arange(4):
                path = '/Data/t%s/%s/%s'\
                    %(str(ind+1),minerva.night,\
                          minerva.cameras[ind].file_name)
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



                



