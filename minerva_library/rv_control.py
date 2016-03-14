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


def rv_observing(minerva):

    # python bug work around -- strptime not thread safe. Must call this once before starting threads    
    junk = datetime.datetime.strptime('2000-01-01 00:00:00','%Y-%m-%d %H:%M:%S')

    mail.send("MINERVA starting observing","Love,\nMINERVA")

    if os.path.exists('sunOverride.txt'): os.remove('sunOverride.txt')
    with open('aqawan1.request.txt','w') as fh:
        fh.write(str(datetime.datetime.utcnow()))

    with open('aqawan2.request.txt','w') as fh:
        fh.write(str(datetime.datetime.utcnow()))

#    minerva.domeControlThread()

    minerva.telescope_initialize(tracking=False,derotate=False)
    minerva.telescope_park()

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
                minerva.site.obs.horizon = '21.0'
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
                            threads.append(threading.Thread(target=newauto.autofocus,args=(minerva,telescope.num,),kwargs=kwargs))
                        for thread in threads(): thread.start()
                        for thread in threads(): thread.join()
                    else:
                        doSpectra(minerva,target,[1,2,3,4])
                else: minerva.logger.info(target['name']+ ' not observable; skipping')


    # all done; close the domes                 
    if os.path.exists('aqawan1.request.txt'): os.remove('aqawan1.request.txt')
    if os.path.exists('aqawan2.request.txt'): os.remove('aqawan2.request.txt')

    minerva.endNight()
    

def doSpectra(minerva, target, tele_list):

    # if after end time, return
    if datetime.datetime.utcnow() > target['endtime']:
        minerva.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + "); skipping")
        return

    # if before start time, wait
    if datetime.datetime.utcnow() < target['starttime']:
        waittime = (target['starttime']-datetime.datetime.utcnow()).total_seconds()
        minerva.logger.info("Target " + target['name'] + " is before its starttime (" + str(target['starttime']) + "); waiting " + str(waittime) + " seconds")
        time.sleep(waittime)

    # if the dome isn't open, wait for it to open
    for dome in minerva.domes:
        while not dome.isOpen():
            minerva.logger.info("Waiting for dome to open")
            if datetime.datetime.utcnow() > target['endtime']: 
                minerva.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + ") while waiting for the dome to open; skipping")
                return
            time.sleep(60)

    # acquire the target for each telescope
    if type(tele_list) is int:
        if (tele_list < 1) or (tele_list > len(minerva.telescopes)):
            tele_list = [x+1 for x in range(len(minerva.telescopes))]
        else:
            tele_list = [tele_list]
    threads = [None] * len(tele_list)
    for t in range(len(tele_list)):
        if minerva.telcom_enabled[tele_list[t]-1]:
            #TODOACQUIRETARGET Needs to be switched to take dictionary argument
            #S i think this might act up due to being a dictionary, but well see.
            # swap the m3port to the imager to locate the fiber
            m3port = minerva.telescopes[tele_list[t]-1].port['IMAGER']
            kwargs = {'tracking':True, 'derotate':False, 'm3port':m3port}
            threads[t] = threading.Thread(target = minerva.telescopes[tele_list[t]-1].acquireTarget,args=(target,),kwargs=kwargs)
            threads[t].start()

    # wait for all telescopes to get to the target
    # TODO: some telescopes could get in trouble and drag down the rest; keep an eye out for that
    minerva.logger.info("Waiting for all telescopes to slew")
    t0 = datetime.datetime.utcnow()
    slewTimeout = 360.0 # sometimes it needs to home as part of a recovery, let it do that
    for thread in threads:
        elapsedTime = (datetime.datetime.utcnow()-t0).total_seconds()
        thread.join(slewTimeout - elapsedTime)

    # see if the thread timed out
    for t in range(len(tele_list)):
        if threads[t].isAlive():
            minerva.logger.error("T" + str(tele_list[t]) + " thread timed out waiting for slew")
            mail.send("T" + str(tele_list[t]) + " thread timed out waiting for slew",
                      "Dear Benevolent Humans,\n\n"+
                      "T" + str(tele_list[t]) + " thread timed out waiting for slew. "+
                      "This shouldn't happen. Please fix me and note what was done."+
                      "Love,\nMINERVA",level='serious')
        
    minerva.logger.info("Locating Fiber")
    backlight(minerva)
    for t in range(len(tele_list)):
        tel_num = tele_list[t]
        telescope = minerva.telescopes[tel_num-1]
        camera = minerva.cameras[tel_num-1]
        
        backlit = glob.glob('/Data/t' + str(tel_num) + '/' + minerva.night + '/*backlight*.fits')
        if len(backlit) > 0:
            xfiber, yfiber = find_fiber(backlit[-1])
            if xfiber <> None:
                minerva.logger.info("T" + str(tel_num) + ": Fiber located at (x,y) = (" + str(xfiber) + "," + str(yfiber) + ") in image " + str(backlit[-1]))
                camera.fau.xfiber = xfiber
                camera.fau.yfiber = yfiber
            else:
                minerva.logger.error("T" + str(tel_num) + ": failed to find fiber in image " + str(backlit[-1]) + "; using default of (x,y) = (" + str(camera.fau.xfiber) + "," + str(camera.fau.yfiber) + ")")
        else:
            minerva.logger.error("T" + str(tel_num) + ": failed to find fiber; using default of (x,y) = (" + str(camera.fau.xfiber) + "," + str(camera.fau.yfiber) + ")")
        camera.fau.guiding=True


    threads = []
    guideThreads = []
    for t in range(len(tele_list)):
        if minerva.telcom_enabled[tele_list[t]-1]:
            #TODOACQUIRETARGET Needs to be switched to take dictionary argument
            #S i think this might act up due to being a dictionary, but well see.
            # swap the m3port to the imager to locate the fiber
            telescope = minerva.telescopes[tele_list[t]-1]
            
            m3port = telescope.port['FAU']
            thread = threading.Thread(target = telescope.m3port_switch, args=(m3port,))
            thread.start()
            threads.append(thread)
            
            thread = threading.Thread(target=minerva.fauguide,args=(target,tele_list[t],))
            thread.start()
            guideThreads.append(thread)

    # wait for all m3 mirrors to finish
    for thread in threads:
        thread.join()

    for t in range(len(tele_list)):
        #TODOACQUIRETARGET Needs to be switched to take dictionary argument
        #S i think this might act up due to being a dictionary, but well see.                
        threads[t] = threading.Thread(target = minerva.pointAndGuide,args=(target,tele_list[t]))
        threads[t].start()
        
    # wait for all telescopes to put target on their fibers (or timeout)
    minerva.logger.info("Waiting for all telescopes to acquire")
    acquired = False
    timeout = 300.0 # is this long enough?
    elapsedTime = 0.0
    t0 = datetime.datetime.utcnow()
    while not acquired and elapsedTime < timeout:
        acquired = True
        for i in range(len(tele_list)):
            minerva.logger.info("T" + str(tele_list[i]) + ": acquired = " + str(minerva.cameras[tele_list[i]-1].fau.acquired))
            if not minerva.cameras[tele_list[i]-1].fau.acquired:
                minerva.logger.info("T" + str(tele_list[i]) + " has not acquired the target yet; waiting (elapsed time = " + str(elapsedTime) + ")")
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
            minerva.stopFAU(tele_list)
            return

        # if the dome isn't open, wait for it to open
        for dome in minerva.domes:
            while not dome.isOpen():
                minerva.logger.info("Waiting for dome to open")
                if datetime.datetime.utcnow() > target['endtime']: 
                    minerva.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + ") while waiting for the dome to open; skipping")
                    minerva.stopFAU(tele_list)
                    return
                time.sleep(60)

        minerva.takeSpectrum(target)

    minerva.stopFAU(tele_list)

    # let's take another backlit image to see how stable it is
    backlight(minerva)

    return

def peakupflux(minerva, target, telnum):

#    minerva.fauguide(target,[telnum], xfiber=camera.fau.xfiber, yfiber=camera.fau.yfiber)
#    aveflux = 

    pass


def endNight(minerva):

    for telescope in minerva.telescopes:
        minerva.endNight(num=int(telescope.num), email=False)
    minerva.endNight(kiwispec=True)

def backlight(minerva, tele_list=0, fauexptime=150.0, stagepos=None, name='backlight'):

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

    #S Zero index the tele_list
    tele_list = [x-1 for x in tele_list]

    # move the iodine stage to the best position for backlighting
    if stagepos == None:
        kwargs = {'locationstr' : 'backlight'}
        threads = [threading.Thread(target=minerva.ctrl_i2stage_move,kwargs=kwargs)]
    else:
        kwargs = {'position':stagepos}
        threads = [threading.Thread(target=minerva.ctrl_i2stage_move,kwargs=kwargs)]
        
    # turn on the slit flat LED
    minerva.spectrograph.led_turn_on()

    # swap to the imaging port to block light from the telescope
    for i in range(len(tele_list)):
        threads.append(threading.Thread(target=minerva.telescopes[tele_list[i]].m3port_switch,
                                        args=[minerva.telescopes[tele_list[i]].port['IMAGER'],]))

    # execute long commands asynchronously
    for thread in threads:
        thread.start()

    # wait for everything to complete
    for thread in threads:
        thread.join()

    # take an exposure with the spectrograph (to trigger the LED)
    kwargs = {'expmeter':None,"exptime":fauexptime+2,"objname":"backlight"}
    spectrum_thread = threading.Thread(target=minerva.spectrograph.take_image, kwargs=kwargs)
    spectrum_thread.start()

    # take images with all FAUs
    fau_threads = []
    for i in range(len(tele_list)):
        kwargs = {'telescope_num':int(minerva.telescopes[tele_list[i]].num)}
        target = {
            'name':name,
            'fauexptime':fauexptime,
            }
        fau_threads.append(threading.Thread(target=minerva.takeFauImage,args=[target,],kwargs=kwargs)) 

    # start all the FAU images
    for fau_thread in fau_threads:
        fau_thread.start()

    # wait for all fau images to complete
    for fau_thread in fau_threads:
        fau_thread.join()

    # wait for spectrum to complete
    spectrum_thread.join()
    
    # delete the spectrograph image
    badfiles = glob.glob('/Data/kiwispec/' + minerva.night + '/*backlight*.fits')
    for badfile in badfiles:
        os.remove(badfile)

    # turn off the slit flat LED
    minerva.spectrograph.led_turn_off()
    minerva.logger.info("Done with backlit images")

# given a backlit FAU image, locate the fiber
def find_fiber(image):
    
    catname = utils.sextract('',image)
    cat = utils.readsexcat(catname)

    # readsexcat will return an empty dictionary if it fails
    # and a dictionary with empty lists if there are no targets
    # both will be caught (and missing key) by this try/except
    try: brightest = np.argmax(cat['FLUX_ISO'])
    except: return None, None

    # if the keys aren't present, it will be caught here
    try: return cat['XWIN_IMAGE'][brightest], cat['YWIN_IMAGE'][brightest]
    except: return None, None

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

    # evaluate stability as a function of alt/az/rotation
    for rotang in range(0,360,10):

        threads = []
        for telescope in minerva.telescopes:
            threads.append(threading.Thread(target=telescope.rotatorMove,args=[rotang,]))
        for thread in threads:
            thread.start()
            
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
#    night = datetime.datetime.utcnow().strftime('%Y%m%d')
    scheduleFile = minerva.base_directory + '/schedule/' + minerva.night + '.kiwispec.txt' 


    sunset = minerva.site.sunset(horizon=-18)
    sunrise = minerva.site.sunrise(horizon=-18)

    num = 3
    
    targets = get_rv_target(minerva)
    bstars = get_rv_target(minerva,bstar=True)

    for target in targets:
        target['num'] = [num]
    for bstar in bstars:
        bstar['num'] = [num]

    acquisitionOverhead = 300.0
    readTime = 21.7
    elapsedTime = 0.0

    print ((sunrise-sunset).total_seconds() + 3600.0)/3600.0

    fh = open(scheduleFile,'w')
    while ((sunrise-sunset).total_seconds() + 3600.0) > elapsedTime:
        for target in targets:
            target['num'] = [num]

            acquisitionTime = acquisitionOverhead + num*(readTime+target['exptime'][0])

            starttime = sunset + datetime.timedelta(seconds=elapsedTime)
            endtime = sunset + datetime.timedelta(seconds=elapsedTime+acquisitionTime)
            if (endtime <= target['endtime'] and starttime >= target['starttime']) or (starttime >= target['starttime'] and target['endtime'] == sunrise):

                target['expectedStart'] = str(sunset + datetime.timedelta(seconds=elapsedTime))
                target['expectedEnd'] = str(sunset + datetime.timedelta(seconds=elapsedTime + acquisitionTime))

                # add a target to the schedule
                elapsedTime += acquisitionTime
                jsonstr = targetlist.target2json(target)
                fh.write(jsonstr + '\n')

                # add a B star to the schedule
                added = False
                for bstar in bstars:
                    acquisitionTime = (acquisitionOverhead + num*(readTime+bstar['exptime'][0]))
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
          
            if ((sunrise-sunset).total_seconds() + 3600.0) < elapsedTime:
                break
        if elapsedTime == 0:
            print "no targets at sunset"
            break

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



                



