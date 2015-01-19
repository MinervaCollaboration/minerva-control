import urllib2, datetime, time
import telnetlib, socket, os
import threading, sys, logging
from win32com.client import Dispatch
import ephem
from xml.etree import ElementTree
import pyfits

Observing = True

night = 'n' + datetime.datetime.utcnow().strftime('%Y%m%d')
datapath = prepNight(night)
logging.basicConfig(filename=datapath + night + '.log', format="%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S", level=logging.DEBUG)
logging.Formatter.converter = time.gmtime

def getWeather():

    # the URL for the machine readable weather page for the Ridge
    url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"

    # read the webpage
    logging.info('Requesting URL: ' + url)
    request = urllib2.Request(url)
    response =  urllib2.urlopen(request)
    data = response.read().split('\n')
    
    # convert the date into a datetime object
    weather = {
        'date':datetime.datetime.strptime(data[0],'%Y, %m, %d, %H, %M, %S, %f')}
    
    # populate the weather dictionary from the webpage
    for parameter in data[1:-1]:
        weather[(parameter.split('='))[0]] = float((parameter.split('='))[1])
        logging.info(parameter)

    weather['sunAltitude'] = sunAltitude()

    # make sure all required keys are present
    requiredKeys = ['totalRain', 'wxt510Rain', 'barometer', 'windGustSpeed', 
                    'outsideHumidity', 'outsideDewPt', 'outsideTemp', 
                    'windSpeed', 'windDirectionDegrees', 'date', 'sunAltitude']
    for key in requiredKeys:
        if not key in weather.keys():
            # if not, return an error
            logging.error('Weather page does not have all required keys')
            return -1

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
        tn = telnetlib.Telnet(IP,port,1)
    except socket.timeout:
        logging.error('Timeout attempting to connect to the aqawan')
        return -1

    tn.write("vt100\r\n")
    tn.write(message + "\r\n")

    response = tn.read_until(b"/r/n/r/n#>",0.5)
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
    return sun.alt

# TODO: open sequentially with status feedback; test carefully!
# sound alarm before opening?
def openAqawan():
    return -1
    if oktoopen():
        logging.info(aqawanCommunicate('OPEN_SHUTTERS'))
#        logging.info(aqawanCommunicate('OPEN_SHUTTER_1'))
#        logging.info(aqawanCommunicate('OPEN_SHUTTER_2'))


# TODO: check to make sure it's not closed, then close, error handling
def closeAqawan():
    
    logging.info(aqawanCommunicate('CLOSE_SEQUENTIAL'))       

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

    # make sure each parameter is within the limits for safe observing
    for key in weatherLimits:
        if weather[key] < weatherLimits[key][0] or weather[key] > weatherLimits[key][1]:
            # will this screw up the asynchronous-ness?
            logging.info('Not OK to open: ' + key + '=' + str(weather[key]) + '; Limits are ' + weatherLimits[key][0], weatherLimits[key][1])
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
    logging.info('Preventing maxim from cloing upon exit')
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

    dirname = "C:/minerva/data/" + night + "/"
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    return dirname

# Returns the next file number given an image directory
def getIndex(dirname):
    files = os.listdir(dirname)

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
        cam.Expose(exptime, DARK)
        while not cam.ImageReady:
            time.sleep(0.1)     
        filename = datapath + "/" + night + ".T3." + objectName + "." + getIndex(datapath) + ".fits"
        cam.SaveImage(filename)

def doSkyFlat(cam):

    minSunAlt = -12
    maxSunAlt = -3

    dither = 3 # arcminutes
    biasLevel = 3200
    targetCounts = 20000
    saturation = 45000
    maxExpTime = 60
    minExpTime = 10

    obs = setObserver()
    sun = ephem.Sun()
   
    # Chase the Sun
    if datetime.datetime.now().hour > 12:
        sunsetting = True
        obs.horizon = maxSunAlt
        flatStartTime = obs.next_setting(sun,start=datetime.datetime.utcnow(), use_center=True).datetime()
        secondsUntilSunset = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0
    else:
        # Sun rising
        sunsetting = False
        obs.horizon = minSunAlt
        flatStartTime = obs.next_rising(sun,start=datetime.datetime.utcnow(), use_center=True).datetime()
        secondsUntilSunrise = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0

    # Wait for twilight
    sunAlt = sunAltitude()
    if sunAlt < minSunAlt:
        if sunSetting:
            logging.info('Sun (' + str(sunAlt) + ') below horizon (' + str(minSunAlt) + ') and setting; skipping skyflats')
            return
        else:
            time.sleep(secondsUntilSunrise)
    else if sunAlt > maxSunAlt:
        if not sunSetting:
            logging.info('Sun (' + str(sunAlt) + ') above horizon (' + str(maxSunAlt) + ') and rising; skipping skyflats')
            return
        else:
            time.sleep(secondsUntilSunset)

    # Now it's within 5 minutes of twilight flats
    logging.info('Beginning twilight flats')

    # Open aqawan
#    openAqawan()

    # Slew to the optimally flat part of the sky
    # See Chromey and Hasselbacher, 1996
    Alt = 75 # degrees (somewhat site dependent)
    Az = SunAz + 180.0 # degrees
    if Az > 360.0:
        Az = Az - 360.0

    mountGotoAltAz(alt,az)
    mountTrackingOn()

    exptime = minExpTime

        
    # Take flat fields
    cam.Expose(exptime, FLAT)
    while not cam.ImageReady:
        time.sleep(0.1)    
    filename = datapath + "/" + night + ".T3.SkyFlat." + getIndex(datapath) + ".fits"
    cam.SaveImage(filename)

    # determine the mode of the image (mode requires scipy, use mean for now...)
    mode = getMean(filename)

    if mode > Saturation:
        # Too much signal
        logging.info("Flat deleted: Mode=" + str(mode) + '; sun altitude=' + str(sunalt) +
                     "; exptime=" + str(exptime) + '; filter = ' + filter)
        os.remove(filename)
    else if mode < 2.0*biaslevel:
        # Too little signal
        logging.info("Flat deleted: Mode=" + str(mode) + '; sun altitude=' + str(sunalt) +
                     "; exptime=" + str(exptime) + '; filter = ' + filter)
        os.remove(filename)
#    else:
        # just right...
        
    # Scale exptime to get a mode of targetCounts in next exposure
    if mode-biaslevel <= 0:
        exptime = maxExpTime
    else:
        exptime = exptime*(targetCounts-biasLevel)/(mode-biasLevel)
        # do not exceed limits
        exptime = max([minexptime,exptime])
        exptime = min([maxexptime,exptime])

    logging.info("Scaling exptime to " + str(exptime))

def doScience(cam, target):

    LIGHT = 1
    mountGotoRaDecJ2000(target['ra'], target['dec'])

    filters = {
        'B' : 0,
        'V' : 1,
        'gp' : 2,
        'rp' : 3,
        'ip' : 4,
        'zp' : 5,
        'air' : 6,
    }   

    while datetime.datetime.utcnow() < target['endtime']:
        cam.Expose(target['exptime'], LIGHT, filters[target['filter']])
        while not cam.ImageReady:
            time.sleep(0.1)     
        filename = datapath + "/" + night + ".T3." + target['name'] + "." + getIndex(datapath) + ".fits"
        cam.SaveImage(filename)
    
def endNight():

    # park the scope
    parkAlt = 60.0
    parkAz = 0.0
    mountGotoAltAz(parkAlt, parkAz)
    mountTrackingOff()

    #TODO: Compress the data

    #TODO: Back up the data
    

if __name__ == '__main__':
    
    # Prepare for the night (define data directories, etc)
    datapath = prepNight()

    # run the aqawan heartbeat and weather checking asynchronously
    aqawanThread = threading.Thread(target=aqawan, args=(), kwargs={})
    aqawanThread.start()

    # Connect to the Camera
    cam = connectCamera()

    # Take biases and darks
    doBias(cam)
    doDark(cam)

    # Take Evening Sky flats
    doSkyFlat(cam)

    obs = setObserver()
    obs.horizon = -6
    sun = ephem.Sun()
    sunrise = obs.next_rising(sun,start=datetime.datetime.utcnow(), use_center=True).datetime()

    target = {
        'name' : 'AlphaCom',
        'ra' : 13.166466, # hours
        'dec' : 17.529431, # degrees
        'exptime' : 10,
        'filter' : 'V',
        'starttime' : datetime.datetime(2015,1,20,5,52,30),
        'endtime' : sunrise,
        }
    
    # Start Science Obs
    doScience(cam, target)

    # Take Morning Sky flats
    doSkyFlat(cam)

    # Take biases and darks
    doDark(cam)
    doBias(cam)

    endNight()
    
    # Stop the aqawan thread
    Observing = False
