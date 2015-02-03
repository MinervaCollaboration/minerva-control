import minerva_class_files as minerva
import ipdb



def aqawanOpen(aqawan):
    pass

def parseTarget(line):

#    # ---- example to create target file ----
#    target = {
#        'name' : 'M77',
#        'ra' : 2.7113055,
#        'dec':-0.013333,
#        'exptime':[240.0,240.0,240.0],
#        'filter':['B','V','rp'],
#        'num':[5,5,5],
#        'starttime': '2015-01-23 05:00:00',
#        'endtime': '2015-01-24 05:00:00',
#        'selfguide': True,
#        'guide':False,
#        'defocus':0.0,
#        'cycleFilter':True,
#    }
#    with open('list.txt','w') as outfile:
#        json.dump(target,outfile)
#    # --------------------------------------

    target = json.loads(line)

    # convert strings to datetime objects
    target['starttime'] = datetime.datetime.strptime(target['starttime'],'%Y-%m-%d %H:%M:%S')
    target['endtime'] = datetime.datetime.strptime(target['endtime'],'%Y-%m-%d %H:%M:%S')

    return target

# should do this asychronously and continuously
def heartbeat(aqawan):
    
    while Observing:
        logger.info(aqawan.heartbeat())
        if not oktoopen(open=True):
            aqawan.close()
        time.sleep(15)

def doScience(enclosure, telescope, camera, target):

    # if after end time, return
    if datetime.datetime.utcnow() > target['endtime']:
        logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + "); skipping")
        return

    # if before start time, wait
    if datetime.datetime.utcnow() < target['starttime']:
        waittime = (target['starttime']-datetime.datetime.utcnow()).total_seconds()
        logger.info("Target " + target['name'] + " is before its starttime (" + str(target['starttime']) + "); waiting " + str(waittime) + " seconds")
        time.sleep(waittime)

    # slew to the target
    telescope.acquireTarget(target['ra'],target['dec'])

    if target['defocus'] <> 0.0:
        logger.info("Defocusing Telescope by " + str(target['defocus']) + ' mm')
        telescope.focuserIncrement(target['defocus']*1000.0)

    # take one in each band, then loop over number (e.g., B,V,R,B,V,R,B,V,R)
    if target['cycleFilter']:
        for i in range(max(target['num'])):
            for j in range(len(target['filter'])):

                # if the enclosure is not open, wait until it is
                while not enclosure.isOpen():
                    response = enclosure.open()
                    if response == -1:
                        logger.info('Enclosure closed; waiting for conditions to improve') 
                        time.sleep(60)
                    if datetime.datetime.utcnow() > target['endtime']: return
                    # reacquire the target
                    if enclosure.isOpen(): telescope.acquireTarget(target['ra'],target['dec'])

                if datetime.datetime.utcnow() > target['endtime']: return
                if i < target['num'][j]:
                        logger.info('Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
                        camera.takeImage(camera.cam, target['exptime'][j], target['filter'][j], target['name'])
                
    else:
        # take all in each band, then loop over filters (e.g., B,B,B,V,V,V,R,R,R) 
        for j in range(len(target['filter'])):
            # cycle by number
            for i in range(target['num'][j]):

                # if the enclosure is not open, wait until it is
                while not enclosure.isOpen():
                    response = enclosure.open()
                    if response == -1:
                        logger.info('Enclosure closed; waiting for conditions to improve') 
                        time.sleep(60)
                    if datetime.datetime.utcnow() > target['endtime']: return
                    # reacquire the target
                    if enclosure.isOpen(): telescope.acquireTarget(target['ra'],target['dec'])
                
                if datetime.datetime.utcnow() > target['endtime']: return
                logger.info('Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
                camera.takeImage(camera.cam, target['exptime'][j], target['filter'][j], target['name'])

 

if __name__ == '__main__':

    # Prepare for the night (define data directories, etc)
    datapath = prepNight()

    # Start a logger
    logging.basicConfig(filename=datapath + night + '.log', format="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S", level=logging.DEBUG)  
    logging.Formatter.converter = time.gmtime

    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
#    # set a format which is simpler for console use
#    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
#    # tell the handler to use this format
#    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)

#    backup()
#    cam = connectCamera()
#    takeImage(cam,0,'B','Bias')
#    ipdb.set_trace()

    # run the aqawan heartbeat and weather checking asynchronously
    aqawanThread = threading.Thread(target=aqawan, args=(), kwargs={})
    aqawanThread.start()

    # Connect to the Camera
    cam = connectCamera()
    mountConnect()

#    ipdb.set_trace()

    # Take biases and darks
    doBias(cam)
    doDark(cam)

    #ipdb.set_trace()

    # keep trying to open the aqawan every minute
    # (probably a stupid way of doing this)
    response = -1
    while response == -1:
        response = openAqawan()
        if response == -1: time.sleep(60)

   # ipdb.set_trace() # stop execution until we type 'cont' so we can keep the dome open 

    flatFilters = ['V']

    # Take Evening Sky flats
    doSkyFlat(cam, flatFilters)

    # Determine sunrise/sunset times
    obs = setObserver()
    obs.horizon = '-12.0'
    sun = ephem.Sun()
    sunrise = obs.next_rising(sun, start=startNightTime, use_center=True).datetime()
    sunset = obs.next_setting(sun, start=startNightTime, use_center=True).datetime()

    timeUntilSunset = (sunset - datetime.datetime.utcnow()).total_seconds()
    if timeUntilSunset > 0:
        logging.info('Waiting for sunset (' + str(timeUntilSunset) + 'seconds)')
        time.sleep(timeUntilSunset)
    
    # find the best focus for the night
    autoFocus()

    #ipdb.set_trace()

    # read the target list
    with open(night + '.txt', 'r') as targetfile:
        for line in targetfile:
            target = parseTarget(line)
            
            # check if the end is before sunrise
            if target['endtime'] > sunrise: 
                target['endtime'] = sunrise
            # check if the start is after sunset
            if target['starttime'] < sunset: 
                target['starttime'] = sunset

            # Start Science Obs
            doScience(cam, target)
    
    # Take Morning Sky flats
    doSkyFlat(cam, flatFilters, morning=True)

    # Want to close the aqawan before darks and biases
    # closeAqawan in endNight just a double check
    closeAqawan()

    # Take biases and darks
    doDark(cam)
    doBias(cam)

    endNight(datapath)
    
    # Stop the aqawan thread
    Observing = False
    
