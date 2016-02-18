import threading
import control
import mail
import ipdb
import datetime
import sys
import ephem
import targetlist
import env
import time

def rv_observing(minerva):

    # python bug work around -- strptime not thread safe. Must call this once before starting threads    
    junk = datetime.datetime.strptime('2000-01-01 00:00:00','%Y-%m-%d %H:%M:%S')

    mail.send("MINERVA starting observing","Love,\nMINERVA")
    
    minerva.domeControlThread()
    minerva.telescope_initialize(tracking=False,derotate=False)
    minerva.telescope_park()

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
                    minerva.doSpectra(target,[1,2,3,4])
                else: minerva.logger.info(target['name']+ ' not observable; skipping')

    minerva.observing=False
    minerva.endNight()
    

def endNight(minerva):

    for telescope in minerva.telescopes:
        minerva.endNight(num=int(telescope.num), email=False)
    minerva.endNight(kiwispec=True)



def backlight(minerva, tele_list=0, fauexptime=150.0, stagepos=None, name='backlight'):

    #S check if tele_list is only an int                                                                                                
    if type(tele_list) is int:
        #S Catch to default a zero arguement or outside array range tele_list                                                       
        #S and if so make it default to controling all telescopes.                                                       
        if (tele_list < 1) or (tele_list > len(minerva.telescopes)):
            #S This is a list of numbers fron 1 to the number scopes                                                            
            tele_list = [x+1 for x in range(len(minerva.telescopes))]
        #S If it is in the range of telescopes, we'll put in a list to                                                              
        #S avoid accessing issues later on.                                                                                         
        else:
            tele_list = [tele_list]

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
    kwargs = {'expmeter':None,"exptime":fauexptime+30,"objname":"backlight"}
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
    
    # turn off the slit flat LED
    minerva.spectrograph.led_turn_off()

    minerva.logger.info("Done with backlit images")
    
    #minerva.takeFauImage({'name':'backlight','fauexptime':1},telescope_num=1)

# given a backlit FAU image, locate the fiber
def find_fiber(image):
    pass
    
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

        starttime = sunset
        endtime = sunrise

        minerva.site.obs.horizon = '21.0'
        body = ephem.FixedBody()
        body._ra = str(target['ra']*15.0)
        body._dec = str(target['dec'])

        #S UTC vs local time not right, but not significant
        body._epoch = datetime.datetime.utcnow()
        body.compute()
                        
        # calculate the object's rise time
        try:
            risetime = minerva.site.obs.next_rising(body,start=minerva.site.NautTwilEnd()).datetime()
        except ephem.AlwaysUpError:
            # if it's always up, don't modify the start time
            risetime = starttime
        except ephem.NeverUpError:
            # if it's never up, skip the target     
            risetime = endtime
 
        # calculate the object's set time
        try:
            settime = minerva.site.obs.next_setting(body,start=minerva.site.NautTwilEnd()).datetime()
        except ephem.AlwaysUpError:
            # if it's always up, don't modify the end time
            settime = endtime
        except ephem.NeverUpError:
            # if it's never up, skip the target
            settime = starttime

        # if it rises before it sets, redo with the previous day
        if risetime > settime:
            try:
                risetime = minerva.site.obs.next_rising(body,start=minerva.site.NautTwilEnd()-datetime.timedelta(days=1)).datetime()
            except ephem.AlwaysUpError:
                # if it's always up, don't modify the start time
                risetime = starttime
            except ephem.NeverUpError:
                # if it's never up, skip the target
                risetime = endtime

        # modify start time to ensure the target is always above the horizon
        if starttime < risetime:
            starttime = risetime
        if endtime > settime:
            endtime = settime

        if starttime < endtime:
            target['starttime'] = starttime
            target['endtime'] = endtime
            
            goodtargets.append(target)

    for target in goodtargets:
        print target['name'] + ' ' + str(target['starttime']) + ' ' + str(target['endtime'])

    return goodtargets
        
def mkschedule(minerva):
#    night = datetime.datetime.utcnow().strftime('%Y%m%d')
    scheduleFile = minerva.base_directory + '/schedule/' + minerva.night + '.kiwispec.txt' 


    sunset = minerva.site.sunset(horizon=-18)
    sunrise = minerva.site.sunrise(horizon=-18)


    targets = get_rv_target(minerva)
    bstars = get_rv_target(minerva,bstar=True)

    acquisitionOverhead = 300.0
    readTime = 21.7
    bstarndx = 0
    nbstars = len(bstars)
    elapsedTime = 0.0

    fh = open(scheduleFile,'w')
    while ((sunrise-sunset).total_seconds() + 3600.0) > elapsedTime:
        for target in targets:
            num = 3
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

                acquisitionTime = (acquisitionOverhead + num*(readTime+bstars[bstarndx]['exptime'][0]))

                bstars[bstarndx]['expectedStart'] = str(sunset + datetime.timedelta(seconds=elapsedTime))
                bstars[bstarndx]['expectedEnd'] = str(sunset + datetime.timedelta(seconds=elapsedTime + acquisitionTime))

                elapsedTime += acquisitionTime
                jsonstr = targetlist.target2json(bstars[bstarndx])
                fh.write(jsonstr + '\n')

                bstarndx = (bstarndx + 1) % nbstars
    fh.close()



if __name__ == "__main__":

    minerva = control.control('control.ini','/home/minerva/minerva-control')

#    endNight(minerva)
#    sys.exit()
    mkschedule(minerva)
#    sys.exit()
    
     
    minerva.telescope_initialize(tracking=False,derotate=False)
    minerva.telescope_park()


#    ipdb.set_trace()
    fiber_stability(minerva)

#    # figure out the optimal stage position for i2 stage during backlighting (81 mm)
#    for i in range(20):
#        backlight(minerva,stagepos=73.0 + float(i), name='backlight' + str(int(73.0 + float(i))))



                



