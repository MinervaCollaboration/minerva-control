import urllib, urllib2, datetime, time
import telnetlib, socket, os, glob, ipdb
import threading, sys, logging
from win32com.client import Dispatch
import ephem, math
from xml.etree import ElementTree
import pyfits
from astropy.time import Time

Observing = True

# reset the night at local 9 am
today = datetime.datetime.utcnow()

if datetime.datetime.now().hour > 9 and datetime.datetime.now().hour < 17:
    today = today + datetime.timedelta(days=1)
night = 'n' + today.strftime('%Y%m%d')

# Telescope communications
HOST = "127.0.0.1" # Localhost
PORT = 44444

######################################################################

def makeUrl(**kwargs):
    """
    Utility function that takes a set of keyword=value arguments
    and converts them into a properly formatted URL to send to PWI.
    For example, calling the function as:
      makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
    will return the string:
      http://127.0.0.1:8080/?device=mount&cmd=move&dec=20+30+40&ra=10+20+30

    Note that spaces have been URL-encoded to "+" characters.
    """

    url = "http://" + HOST + ":" + str(PORT) + "/?"
    url = url + urllib.urlencode(kwargs.items())
    return url

def pwiRequest(**kwargs):
    """
    Issue a request to PWI using the keyword=value parameters
    supplied to the function, and return the response received from
    PWI.

    For example:
      makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
    will request a slew to J2000 coordinates 10:20:30, 20:30:40, and will
    (under normal circumstances) return the status of the telescope as an
    XML string.
    """

    url = makeUrl(**kwargs)
    return urllib.urlopen(url).read()

def pwiRequestAndParse(**kwargs):
    """
    Works like pwiRequest(), except returns a parsed XML object rather
    than XML text
    """

    return parseXml(pwiRequest(**kwargs))

def parseXml(xml):
    """
    Convert the XML into a smart structure that can be navigated via
    the tree of tag names; e.g. "status.mount.ra"
    """

    return elementTreeToObject(ElementTree.fromstring(xml))

### Status wrappers #####################################

def getStatusXml():
    """
    Return a string containing the XML text representing the status of the telescope
    """

    return pwiRequest(cmd="getsystem")

def getStatus():
    """
    Return a status object representing the tree structure of the XML text.
    Example: getStatus().mount.tracking --> "False"
    """

    return parseXml(getStatusXml())

### High-level command wrappers begin here ##############

### FOCUSER ###

def focuserConnect(port=1):
    """
    Connect to the focuser on the specified Nasmyth port (1 or 2).
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="connect")

def focuserDisconnect(port=1):
    """
    Disconnect from the focuser on the specified Nasmyth port (1 or 2).
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="disconnect")

def focuserMove(position, port=1):
    """
    Move the focuser to the specified position in microns
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="move", position=position)

def focuserIncrement(offset, port=1):
    """
    Offset the focuser by the specified amount, in microns
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="move", increment=offset)

def focuserStop(port=1):
    """
    Halt any motion on the focuser
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="stop")

def startAutoFocus():
    """
    Begin an AutoFocus sequence for the currently active focuser
    """

    return pwiRequestAndParse(device="focuser", cmd="startautofocus")

### ROTATOR ###

def rotatorMove(position, port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="move", position=position)

def rotatorIncrement(offset, port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="move", increment=offset)

def rotatorStop(port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="stop")

def rotatorStartDerotating(port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="derotatestart")

def rotatorStopDerotating(port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="derotatestop")

### MOUNT ###

def mountConnect():
    return pwiRequestAndParse(device="mount", cmd="connect")

def mountDisconnect():
    return pwiRequestAndParse(device="mount", cmd="disconnect")

def mountEnableMotors():
    return pwiRequestAndParse(device="mount", cmd="enable")

def mountDisableMotors():
    return pwiRequestAndParse(device="mount", cmd="disable")

def mountOffsetRaDec(deltaRaArcseconds, deltaDecArcseconds):
    return pwiRequestAndParse(device="mount", cmd="move", incrementra=deltaRaArcseconds, incrementdec=deltaDecArcseconds)

def mountOffsetAltAz(deltaAltArcseconds, deltaAzArcseconds):
    return pwiRequestAndParse(device="mount", cmd="move", incrementazm=deltaAzArcseconds, incrementalt=deltaAltArcseconds)

def mountGotoRaDecApparent(raAppHours, decAppDegs):
    """
    Begin slewing the telescope to a particular RA and Dec in Apparent (current
    epoch and equinox, topocentric) coordinates.

    raAppHours may be a number in decimal hours, or a string in "HH MM SS" format
    decAppDegs may be a number in decimal degrees, or a string in "DD MM SS" format
    """

    return pwiRequestAndParse(device="mount", cmd="move", ra=raAppHours, dec=decAppDegs)

def mountGotoRaDecJ2000(ra2000Hours, dec2000Degs):
    """
    Begin slewing the telescope to a particular J2000 RA and Dec.
    ra2000Hours may be a number in decimal hours, or a string in "HH MM SS" format
    dec2000Degs may be a number in decimal degrees, or a string in "DD MM SS" format
    """
    return pwiRequestAndParse(device="mount", cmd="move", ra2000=ra2000Hours, dec2000=dec2000Degs)

def mountGotoAltAz(altDegs, azmDegs):
    return pwiRequestAndParse(device="mount", cmd="move", alt=altDegs, azm=azmDegs)

def mountStop():
    return pwiRequestAndParse(device="mount", cmd="stop")

def mountTrackingOn():
    return pwiRequestAndParse(device="mount", cmd="trackingon")

def mountTrackingOff():
    return pwiRequestAndParse(device="mount", cmd="trackingoff")

def mountSetTracking(trackingOn):
    if trackingOn:
        mountTrackingOn()
    else:
        mountTrackingOff()

def mountSetTrackingRateOffsets(raArcsecPerSec, decArcsecPerSec):
    """
    Set the tracking rates of the mount, represented as offsets from normal
    sidereal tracking in arcseconds per second in RA and Dec.
    """
    return pwiRequestAndParse(device="mount", cmd="trackingrates", rarate=raArcsecPerSec, decrate=decArcsecPerSec)

def mountSetPointingModel(filename):
    return pwiRequestAndParse(device="mount", cmd="setmodel", filename=filename)

### M3 ###

def m3SelectPort(port):
    return pwiRequestAndParse(device="m3", cmd="select", port=port)

def m3Stop():
    return pwiRequestAndParse(device="m3", cmd="stop")



### XML Parsing Utilities ##################################

class Status: 
    """
    Contains a node (and possible sub-nodes) in the parsed XML status tree.
    Properties are added to the class by the elementTreeToObject function.
    """

    def __str__(self):
        result = ""
        for k,v in self.__dict__.items():
            result += "%s: %s\n" % (k, str(v))

        return result

def elementTreeToObject(elementTreeNode):
    """
    Recursively convert an ElementTree node to a hierarchy of objects that allow for
    easy navigation of the XML document. For example, after parsing:
      <tag1><tag2>data</tag2><tag1> 
    You could say:
      xml.tag1.tag2   # evaluates to "data"
    """

    if len(elementTreeNode) == 0:
        return elementTreeNode.text

    result = Status()
    for childNode in elementTreeNode:
        setattr(result, childNode.tag, elementTreeToObject(childNode))

    result.value = elementTreeNode.text

    return result


def getWeather():

    # the URL for the machine readable weather page for the Ridge
    url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"

    # read the webpage
    logging.info('Requesting URL: ' + url)
    request = urllib2.Request(url)
    try:
        response = urllib2.urlopen(request)
    except:
        logging.error('Error reading the weather page: ' + sys.exc_info()[0])
        return -1
    
    data = response.read().split('\n')
    
    # convert the date into a datetime object
    weather = {
        'date':datetime.datetime.strptime(data[0],'%Y, %m, %d, %H, %M, %S, %f')}
    
    # populate the weather dictionary from the webpage
    for parameter in data[1:-1]:
        weather[(parameter.split('='))[0]] = float((parameter.split('='))[1])
#        logging.info(parameter)

    weather['sunAltitude'] = sunAltitude()

    # make sure all required keys are present
    pageError = False
    requiredKeys = ['totalRain', 'wxt510Rain', 'barometer', 'windGustSpeed', 
                    'outsideHumidity', 'outsideDewPt', 'outsideTemp', 
                    'windSpeed', 'windDirectionDegrees', 'date', 'sunAltitude']
    for key in requiredKeys:
        if not key in weather.keys():
            # if not, return an error
            logging.error('Weather page does not have all required keys (' + key + ')')
            pageError = True

    if pageError: return -1


    # if everything checks out, return the weather
    return weather



def aqawanCommunicate(message):

    messages = ['HEARTBEAT','STOP','OPEN_SHUTTERS','CLOSE_SHUTTERS',
                'CLOSE_SEQUENTIAL','OPEN_SHUTTER_1','CLOSE_SHUTTER_1',
                'OPEN_SHUTTER_2','CLOSE_SHUTTER_2','LIGHTS_ON','LIGHTS_OFF',
                'ENC_FANS_HI','ENC_FANS_MED','ENC_FANS_LOW','ENC_FANS_OFF',
                'PANEL_LED_GREEN','PANEL_LED_YELLOW','PANEL_LED_RED',
                'PANEL_LED_OFF','DOOR_LED_GREEN','DOOR_LED_YELLOW',
                'DOOR_LED_RED','DOOR_LED_OFF','SON_ALERT_ON',
                'SON_ALERT_OFF','LED_STEADY','LED_BLINK',
                'MCB_RESET_POLE_FANS','MCB_RESET_TAIL_FANS',
                'MCB_RESET_OTA_BLOWER','MCB_RESET_PANEL_FANS',
                'MCB_TRIP_POLE_FANS','MCB_TRIP_TAIL_FANS',
                'MCB_TRIP_PANEL_FANS','STATUS','GET_ERRORS','GET_FAULTS',
                'CLEAR_ERRORS','CLEAR_FAULTS','RESET_PAC']

    # not an allowed message
    if not message in messages:
       logging.error('Message not recognized: ' + message)
       return -1

    IP = '192.168.1.14'
    port = 22004
    try:
        tn = telnetlib.Telnet(IP,port,5)
    except socket.timeout:
        logging.error('Timeout attempting to connect to the aqawan')
        return -1

    tn.write("vt100\r\n")

    response = ''
    while response == '':    
        tn.write(message + "\r\n")
        response = tn.read_until(b"/r/n/r/n#>",5)

    logging.info('Response from command ' + message + ': ' + response)
    tn.close()
    return response

    return response.split("=")[1].split()[0]
    return tn.read_all()

    time.sleep(2)

# should do this asychronously and continuously
def aqawan():

    while Observing:            
        logging.info(aqawanCommunicate('HEARTBEAT'))
        if not oktoopen():
            closeAqawan()
        time.sleep(15)
        
def setObserver():
    obs = ephem.Observer()

    # MINERVA latitude/longitude at Mt. Hopkins
    obs.lat = ephem.degrees('31.680407') # N
    obs.lon = ephem.degrees('-110.878977') # E
    obs.elevation = 2316.0 # meters
    return obs

def sunAltitude():

    obs = setObserver()
    obs.date = datetime.datetime.utcnow()
    sun = ephem.Sun()
    sun.compute(obs)
    return float(sun.alt)*180.0/math.pi

def sunAzimuth():

    obs = setObserver()
    obs.date = datetime.datetime.utcnow()
    sun = ephem.Sun()
    sun.compute(obs)
    return float(sun.az)*180.0/math.pi

def aqawanStatus():

    response = aqawanCommunicate('STATUS').split(',')
    status = {}
    for entry in response:
        if '=' in entry:
            status[(entry.split('='))[0].strip()] = (entry.split('='))[1].strip()

#    if status['ERROR'] == 'TRUE':
#        logging.warning('Error condition exists in the PAC')
#        logging.warning(aqawanCommunicate('GET_ERRORS'))
#    if status['FAULT'] == 'TRUE':
#        logging.warning('Fault condition exists in the PAC')
#        logging.warning(aqawanCommunicate('GET_FAULTS'))

    return status

# Open a shutter of the aqawan
def openShutter(shutter):

    # make sure this is an allowed shutter
    if shutter not in [1,2]:
        logging.info('Invalid shutter specified (' + str(shutter) + ')')
        return -1

    status = aqawanStatus()
    timeout = 180.0
    elapsedTime = 0.0

    # if it's already open, return
    if status['Shutter' + str(shutter)] == 'OPEN':
        logging.info('Shutter' + str(shutter) + ' already open')
        return

    # park the telescopes to make sure they're safe from falling debris
    parkScope()

    # open the shutter
    start = datetime.datetime.utcnow()
    response = aqawanCommunicate('OPEN_SHUTTER_' + str(shutter))                
    logging.info(response)
    if not 'Success=TRUE' in response:
        # did the command fail?
        logging.warning('Failed to open shutter ' + str(shutter) + ': ' + response)
        ipdb.set_trace()
        # need to reset the PAC? ("Enclosure not in AUTO"?)
            
    # Wait for it to open
    status = aqawanStatus()
    while status['Shutter' + str(shutter)] == 'OPENING' and elapsedTime < timeout:
        status = aqawanStatus()
        elapsedTime = (datetime.datetime.utcnow()-start).total_seconds()

    # Did it fail to open?
    if status['Shutter' + str(shutter)] <> 'OPEN':
        logging.error('Error opening Shutter ' + str(shutter) )
        return -1

    logging.info('Shutter ' + str(shutter) + ' open')

# Open the aqawan shutters sequentially
def openAqawan():
    if oktoopen():
        # Open Shutter 1
        response = openShutter(1)
        if response == -1: return -1

        # Open Shutter 2
        response = openShutter(2)
        if response == -1: return -1
    else: return -1


# TODO: check to make sure it's not closed, then close, error handling
def closeAqawan():

    timeout = 500
    elapsedTime = 0
    status = aqawanStatus()
    if status['Shutter1'] == "CLOSED" and status['Shutter2'] == "CLOSED":
        logging.info('Both shutters already closed')
    else:
        response = aqawanCommunicate('CLOSE_SEQUENTIAL')
        if not 'Success=TRUE' in response:
            logging.error('Aqawan failed to close!')
            # need to send alerts, attempt other stuff
#            email('Aqawan failed to close!')
        else:
            logging.info(response)    
            start = datetime.datetime.utcnow()
            while status['Shutter1'] <> "CLOSED" and status['Shutter2'] <> "CLOSED" and elapsedTime < timeout:
                elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
                status = aqawanStatus()
            if status['Shutter1'] <> "CLOSED" or status['Shutter2'] <> "CLOSED":
                logging.error('Aqawan failed to close!')
                # need to send alerts, attempt other stuff
                
def oktoopen():
    retval = True    

    # define the safe limits [min,max] for each weather parameter
    weatherLimits = {
        'totalRain':[0.0,1000.0],
        'wxt510Rain':[0.0,0.0], 
        'barometer':[0,2000], 
        'windGustSpeed':[0.0,30.0], 
        'outsideHumidity':[0.0,75.0], 
        'outsideDewPt':[-20.0,50.0],
        'outsideTemp':[-20.0,50.0], 
        'windSpeed':[0.0,30.0], 
        'windDirectionDegrees':[0.0,360.0],
        'date':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
        'sunAltitude':[-90,6],
        }

    # get the current weather, timestamp, and Sun's position
    weather = getWeather()
    while weather == -1:
        time.sleep(1)
        weather = getWeather()

    # make sure each parameter is within the limits for safe observing
    for key in weatherLimits:
        if weather[key] < weatherLimits[key][0] or weather[key] > weatherLimits[key][1]:
            # will this screw up the asynchronous-ness?
            logging.info('Not OK to open: ' + key + '=' + str(weather[key]) + '; Limits are ' + str(weatherLimits[key][0]) + ',' + str(weatherLimits[key][1]))
            retval = False

    return retval

def connectCamera():

    setTemp = -30
    maxCooling = 50
    settleTime = 600
    xbin = 1
    ybin = 1
    x1 = 0
    y1 = 0

    # Connect to an instance of Maxim's camera control.
    # (This launches the app if needed)
    logging.info('Connecting to Maxim') 
    cam = Dispatch("MaxIm.CCDCamera")

    # Connect to the camera 
    logging.info('Connecting to camera') 
    cam.LinkEnabled = True

    # Prevent the camera from disconnecting when we exit
    logging.info('Preventing the camera from disconnecting when we exit') 
    cam.DisableAutoShutdown = True

    # If we were responsible for launching Maxim, this prevents
    # Maxim from closing when our application exits
    logging.info('Preventing maxim from closing upon exit')
    maxim = Dispatch("MaxIm.Application")
    maxim.LockApp = True

    # Set binning
    logging.info('Setting binning to ' + str(xbin) + ',' + str(ybin) )
    cam.BinX = xbin
    cam.BinY = ybin

    # Set to full frame
    xsize = cam.CameraXSize
    ysize = cam.CameraYSize
    logging.info('Setting subframe to [' + str(x1) + ':' + str(x1 + xsize -1) + ',' +
                 str(y1) + ':' + str(y1 + ysize -1) + ']')

    cam.StartX = 0 #int((cam.CameraXSize/cam.BinX-CENTER_SUBFRAME_WIDTH)/2)
    cam.StartY = 0 #int((cam.CameraYSize/cam.BinY-CENTER_SUBFRAME_HEIGHT)/2)
    cam.NumX = xsize # CENTER_SUBFRAME_WIDTH
    cam.NumY = ysize # CENTER_SUBFRAME_HEIGHT

    # Set temperature
    weather = getWeather()
    if weather['outsideTemp'] > (setTemp + maxCooling):
        logging.error('The outside temperature (' + str(weather['outsideTemp']) + ' is too warm to achieve the set point (' + str(setTemp) + ')')
        return -1

    start = datetime.datetime.utcnow()

    logging.info('Turning cooler on')
    cam.TemperatureSetpoint = setTemp
    cam.CoolerOn = True
    currentTemp = cam.Temperature
    elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()

    # Wait for temperature to settle (timeout of 10 minutes)
    while elapsedTime < settleTime and (abs(setTemp - currentTemp) > 0.5):    
        logging.info('Current temperature (' + str(currentTemp) + ') not at setpoint (' + str(setTemp) +
                     '); waiting for CCD Temperature to stabilize (Elapsed time: ' + str(elapsedTime) + ' seconds)')
        time.sleep(10)
        currentTemp = cam.Temperature
        elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()

    # Failed to reach setpoint
    if (abs(setTemp - currentTemp)) > 0.5:
        logging.error('The camera was unable to reach its setpoint (' + str(setTemp) + ') in the elapsed time (' + str(elapsedTime) + ' seconds)')
        return -1

    return cam

#def doBias()

def prepNight():

    dirname = "E:/" + night + "/"
    
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    return dirname

# Returns the next file number given an image directory
def getIndex(dirname):
    files = glob.glob(dirname + "/*.fits")

    return str(len(files)+1).zfill(4)

    if len(files) == 0:
        return '0001'

    lastnum = (files[-1].split('.'))[-2]
    index = str(int(lastnum) + 1).zfill(4)
    return index

def getMean(filename):
    image = pyfits.getdata(filename,0)
    return image.mean()

def doBias(cam, num=11):
    doDark(cam,exptime=0,num=num)

def doDark(cam, exptime=60, num=11):

    DARK = 0
    if exptime == 0:
        objectName = 'Bias'
    else:
        objectName = 'Dark'

    # Take num Dark frames
    for x in range(num):
        logging.info('Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + str(exptime) + ')')
        takeImage(cam,exptime,'V',objectName)

def doSkyFlat(cam, filters, morning=False, num=11):

    minSunAlt = -12
    maxSunAlt = 0

    biasLevel = 3200
    targetCounts = 10000
    saturation = 45000
    maxExpTime = 60
    minExpTime = 10

    obs = setObserver()
    sun = ephem.Sun()
   
    # can we actually do flats right now?
    if datetime.datetime.now().hour > 12:
        # Sun setting (evening)
        if morning:
            logging.info('Sun setting and morning flats requested; skipping')
            return
        obs.horizon = str(maxSunAlt)
        flatStartTime = obs.next_setting(sun,start=datetime.datetime.utcnow(), use_center=True).datetime()
        secondsUntilTwilight = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0
    else:
        # Sun rising (morning)
        if not morning:
            logging.info('Sun rising and evening flats requested; skipping')
            return
        obs.horizon = str(minSunAlt)
        flatStartTime = obs.next_rising(sun,start=datetime.datetime.utcnow(), use_center=True).datetime()
        secondsUntilTwilight = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0

    # wait for twilight
    if secondsUntilTwilight > 0 and (sunAltitude() < minSunAlt or sunAltitude() > maxSunAlt):
        logging.info('Waiting ' +  str(secondsUntilTwilight) + ' seconds until Twilight')
        time.sleep(secondsUntilTwilight)

    # Now it's within 5 minutes of twilight flats
    logging.info('Beginning twilight flats')

    # make sure the telescope/dome is ready for obs
    initializeScope()
    
    # start off with the extreme exposure times
    if morning: exptime = maxExpTime
    else: exptime = minExpTime
  
    # filters ordered from least transmissive to most transmissive
    # flats will be taken in this order (or reverse order in the evening)
    masterfilters = ['H-Beta','H-Alpha','Ha','Y','U','up','zp','zs','B','I','ip','V','rp','R','gp','w','solar','air']
    masterfilters = ['rp','V','B']
#    if not morning: masterfilters = masterfilters.reverse()

    for filterInd in masterfilters:
        if filterInd in filters:
        
            for i in range(num):

                # Slew to the optimally flat part of the sky (Chromey & Hasselbacher, 1996)
                Alt = 75.0 # degrees (somewhat site dependent)
                Az = sunAzimuth() + 180.0 # degrees
                if Az > 360.0: Az = Az - 360.0
            
                # keep slewing to the optimally flat part of the sky (dithers too)
                logging.info('Slewing to the optimally flat part of the sky (alt=' + str(Alt) + ', az=' + str(Az) + ')')
                mountGotoAltAz(Alt,Az)
            
                # Take flat fields
                filename = takeImage(cam, exptime, filterInd, 'SkyFlat')
                
                # determine the mode of the image (mode requires scipy, use mean for now...)
                mode = getMean(filename)
                logging.info("image " + str(i) + " of " + str(num) + " in filter " + filterInd + "; " + filename + ": mode = " + str(mode))
                if mode > saturation:
                    # Too much signal
                    logging.info("Flat deleted: Mode=" + str(mode) + '; sun altitude=' + str(sunalt) +
                                 "; exptime=" + str(exptime) + '; filter = ' + filter)
                    os.remove(filename)
                    i = i-1
                    if exptime == minExpTime and morning:
                        logging.info("Exposure time at minimum, image saturated, and getting brighter; skipping remaining exposures in filter " + filterInd)
                        break
                elif mode < 2.0*biasLevel:
                    # Too little signal
                    i = i-1
                    logging.info("Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) + '; sun altitude=' + str(sunAltitude()) +
                                 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
                    os.remove(filename)
                    if exptime == maxExpTime and not morning:
                        logging.info("Exposure time at maximum, not enough counts, and getting darker; skipping remaining exposures in filter " + filterInd)
                        break
 #              else:
 #                  just right...
        
                # Scale exptime to get a mode of targetCounts in next exposure
                if mode-biasLevel <= 0:
                    exptime = maxExpTime
                else:
                    exptime = exptime*(targetCounts-biasLevel)/(mode-biasLevel)
                    # do not exceed limits
                    exptime = max([minExpTime,exptime])
                    exptime = min([maxExpTime,exptime])
                    logging.info("Scaling exptime to " + str(exptime))

def takeImage(cam, exptime, filterInd, objname):

    exptypes = {
        'Dark' : 0,
        'Bias' : 0,
        'SkyFlat' : 1,
        }

    if objname in exptypes.keys():
        exptype = exptypes[objname]
    else: exptype = 1 # science exposure

    filters = {
        'B' : 0,
        'V' : 1,
        'gp' : 2,
        'rp' : 3,
        'ip' : 4,
        'zp' : 5,
        'air' : 6,
        }   
   
    # Take flat fields
    cam.Expose(exptime, exptype, filters[filterInd])
    while not cam.ImageReady:
        time.sleep(0.1)    

    # Save the image
    filename = datapath + "/" + night + ".T3." + objname + "." + getIndex(datapath) + ".fits"
    logging.info('Saving image: ' + filename)
    cam.SaveImage(filename)

    return filename

def initializeScope():
    # Open aqawan
    logging.info('Opening Aqawan')
    openAqawan()

    # turning on mount tracking
    logging.info('Turning mount tracking on')
    mountTrackingOn()
    
    # turning on rotator tracking
    logging.info('Turning rotator tracking on')
    rotatorStartDerotating()
    
def parseTargetLine(line):
    desc = ['name','ra','dec','exptime','filter','starttime','endtime']
    splitline = line.strip().split(',')
    splitline[0] = splitline[0].lstrip() # name
    splitline[1] = float(splitline[1]) # ra
    splitline[2] = float(splitline[2]) # dec
    splitline[3] = int(splitline[3]) # exptime
    splitline[4] = splitline[4].lstrip() # filter
    splitline[5] = Time(float(splitline[5]), scale='utc', format='jd').datetime # starttime
    splitline[6] = Time(float(splitline[6]), scale='utc', format='jd').datetime # endtime
    return dict(zip(desc, splitline))

def doScience(cam, target):

    initializeScope()

    logging.info("Starting slew to J2000 " + str(target['ra']) + ',' + str(target['dec']))
    mountGotoRaDecJ2000(target['ra'], target['dec'])
    logging.info("Finished slew to J2000 " + str(target['ra']) + ',' + str(target['dec']))

    while datetime.datetime.utcnow() < target['endtime']:
        logging.info('Beginning ' + str(target['exptime']) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'] + ' band') 
        takeImage(cam, target['exptime'], target['filter'], target['name'])

def doPretty(cam, target, RequestedFilters=['B','V','rp'], num=5):

    # Wait until the start time
    timeUntilStart = (target['starttime'] - datetime.datetime.utcnow()).total_seconds()
    if timeUntilStart > 0:
        logging.info("Started before start time; waiting " + str(timeUntilStart) + ' seconds')
        time.sleep(timeUntilStart)

    # definition of "Light" exposure for maxim
    LIGHT = 1 

    # Slew the telescope to the target
    logging.info("Starting slew to J2000 " + str(target['ra']) + ',' + str(target['dec']))
    mountGotoRaDecJ2000(target['ra'], target['dec'])
    logging.info("Finished slew to J2000 " + str(target['ra']) + ',' + str(target['dec']))

    # Static definition of the filters (is there a function to query these?)
    filters = {
        'B'   : 0,
        'V'   : 1,
        'gp'  : 2,
        'rp'  : 3,
        'ip'  : 4,
        'zp'  : 5,
        'air' : 6,
    }

    # Check to make sure the requested filter is available
    if not target['filter'] in filters.keys():
        logging.error("Requested filter (" + target['filter'] + " not available")
        return -1

    for filterInd in RequestedFilters:
        for i in range(num):
            logging.info('Beginning ' + str(target['exptime']) + ' second exposure of ' + target['name'] + ' in the ' + filterInd + ' band')       
            cam.Expose(target['exptime'], LIGHT, filters[filterInd])
            while not cam.ImageReady:
                time.sleep(0.1)     
            filename = datapath + "/" + night + ".T3." + target['name'] + "." + filterInd + "." + getIndex(datapath) + ".fits"
            # Save the image
            logging.info("Saving image: " + filename)
            cam.SaveImage(filename)

def parkScope():
    # park the scope
    parkAlt = 45.0
    parkAz = 180.0

    logging.info('Parking telescope (alt=' + str(parkAlt) + ', az=' + str(parkAz) + ')')
    mountGotoAltAz(parkAlt, parkAz)

    logging.info('Turning mount tracking off')
    mountTrackingOff()
    
    logging.info('Turning rotator tracking off')
    rotatorStopDerotating()
    
def endNight():

    # park the scope
    parkScope()

    # Close the aqawan
    closeAqawan()
    
    #TODO: Compress the data

    #TODO: Back up the data
    


if __name__ == '__main__':
    
    # Prepare for the night (define data directories, etc)
    datapath = prepNight()

    # Start a logger
    logging.basicConfig(filename=datapath + night + '.log', format="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S", level=logging.DEBUG)  
    logging.Formatter.converter = time.gmtime

    # run the aqawan heartbeat and weather checking asynchronously
    aqawanThread = threading.Thread(target=aqawan, args=(), kwargs={})
    aqawanThread.start()

    # Connect to the Camera
    cam = connectCamera()
    mountConnect()

    # Take biases and darks
#    doBias(cam)
#    doDark(cam)

    # keep trying to open the aqawan every minute
    # (probably a stupid way of doing this)
    response = -1
    while response == -1:
        response = openAqawan()
        if response == -1: time.sleep(60)

    #ipdb.set_trace() # stop execution until we type 'cont' so we can keep the dome open 

    # Take Evening Sky flats
    doSkyFlat(cam, ['B','V','rp'])

    ipdb.set_trace()

    obs = setObserver()
    obs.horizon = '-6.0'
    sun = ephem.Sun()
    sunrise = obs.next_rising(sun,start=datetime.datetime.utcnow(), use_center=True).datetime()

    # Should be replaced by a function getTarget() that calls
    # Sam's scheduler
    with open('targets.list', 'r') as targetfile:
    next(targetfile) # skip the header line
    for line in targetfile:
        target = parseTargetLine(line)
        if target['endtime'] > sunrise: # check if the end is after sunrise
            target['endtime'] = sunrise
        # Start Science Obs
        doScience(cam, target)

    # Take pretty pictures
    RequestedFilters = ['B','V','rp']
    num = 3
    
    #focuserConnect()
    #focuserMove(25500) # To get close to reasonable. Probably not a good general postion
    #startAutoFocus()

    #doPretty(cam, target, RequestedFilters=RequestedFilters, num=num)

    # Take Morning Sky flats
    #doSkyFlat(cam, ['V'], morning=True)

    # Take biases and darks
    #doDark(cam)
    #doBias(cam)

    endNight()
    
    # Stop the aqawan thread
    Observing = False
