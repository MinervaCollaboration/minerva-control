from configobj import ConfigObj
import datetime, logging, ipdb
import ephem, time, math, os, sys, json, urllib2
from paramiko import SSHClient, AutoAddPolicy
from scp import SCPClient
class site:

    def __init__(self,site_name, night, configfile=''):

        self.name = site_name

        #set appropriate parameter based on aqawan_num
        #create configuration file object 
        configObj = ConfigObj(configfile)
        
        try:
            siteconfig = configObj[self.name]
        except:
            print('ERROR accessing ', self.name, ".", 
                self.name, " was not found in the configuration file", configfile)
            return 

        self.latitude = siteconfig['Setup']['LATITUDE']
        self.longitude = siteconfig['Setup']['LONGITUDE']        
        self.elevation = float(siteconfig['Setup']['ELEVATION'])
        self.enclosures = siteconfig['Setup']['ENCLOSURES']

        self.currentStatusFile = 'current_' + site_name + '.log'
        self.observing = True
        self.weather = -1
        self.startNightTime = -1
        self.night = night
        
        # touch a file in the current directory to enable cloud override
        self.cloudOverride = os.path.isfile('cloudOverride.txt') 
        self.sunOverride = os.path.isfile('sunOverride.txt')

        logger_name = siteconfig['Setup']['LOGNAME']
        log_file = 'logs/' + night + '/' + siteconfig['Setup']['LOGFILE']

        self.obs = ephem.Observer()
        self.obs.lat = ephem.degrees(str(self.latitude)) # N
        self.obs.lon = ephem.degrees(str(self.longitude)) # E
        self.obs.elevation = self.elevation # meters

        # define more conservative limits to open to prevent cycling when borderline conditions
        self.openLimits = {
            'totalRain':[0.0,1000.0],
            'wxt510Rain':[0.0,0.0], 
            'barometer':[0,2000], 
            'windGustSpeed':[0.0,35.0], 
            'outsideHumidity':[0.0,75.0], 
            'outsideDewPt':[-100.0,100.0],
            'outsideTemp':[-20.0,50.0], 
            'windSpeed':[0.0,30.0], 
            'windDirectionDegrees':[0.0,360.0],
            'date':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
            'sunAltitude':[-90,6],
            'relativeSkyTemp':[-999,-37],
            'cloudDate':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
            }

        self.closeLimits = {
            'totalRain':[0.0,1000.0],
            'wxt510Rain':[0.0,0.0], 
            'barometer':[0,2000], 
            'windGustSpeed':[0.0,40.0], 
            'outsideHumidity':[0.0,80.0], 
            'outsideDewPt':[-100.0,100.0],
            'outsideTemp':[-30.0,60.0], 
            'windSpeed':[0.0,35.0], 
            'windDirectionDegrees':[0.0,360.0],
            'date':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
            'sunAltitude':[-90,6],
            'relativeSkyTemp':[-999,-40],
            'cloudDate':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
            }
        
	# setting up site logger
        fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
        datefmt = "%Y-%m-%dT%H:%M:%S"

        self.logger = logging.getLogger(logger_name)
        formatter = logging.Formatter(fmt,datefmt=datefmt)
        formatter.converter = time.gmtime
        
        fileHandler = logging.FileHandler(log_file, mode='a')
        fileHandler.setFormatter(formatter)

        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(logging.INFO)
        
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(fileHandler)
        self.logger.addHandler(console)

	
##	self.logger = logging.getLogger(logger_name)
##        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
##        formatter.converter = time.gmtime
##	fileHandler = logging.FileHandler(log_file, mode='a')
##	fileHandler.setFormatter(formatter)
##	streamHandler = logging.StreamHandler()
##	streamHandler.setFormatter(formatter)
##
##	self.logger.setLevel(logging.DEBUG)
##	self.logger.addHandler(fileHandler)
##	self.logger.addHandler(streamHandler)

    def status(self):
        self.getWeather()

        status = deepcopy(self.weather)
        status['sunrise'] = self.sunrise()
        status['sunset'] = self.sunset()
        status['NautTwilBegin'] = self.NautTwilBegin()
        status['NautTwilEnd'] = self.NautTwilEnd()
        status['sunalt'] = self.sunalt()
        status['sunaz'] = self.sunaz()
        status['cloudDate'] = str(status['cloudDate'])
        status['date'] = str(status['date'])

        with open(self.currentStatusFile,'w') as outfile:
            json.dump(status,outfile)
            
        return status
            
    def getWeather(self):

        if self.name == 'Mount_Hopkins':
            # the URL for the machine readable weather page for the Ridge
            url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"

            # read the webpage
            self.logger.debug('Requesting URL: ' + url)
            request = urllib2.Request(url)
            try:
                response = urllib2.urlopen(request)
            except urllib2.HTTPError:
                self.logger.debug('HTTPError while reading the weather page')
                self.weather = -1
                return
            except:
                self.logger.error('Error reading the weather page: ' + str(sys.exc_info()[0]))
                self.weather = -1
                return
            
            data = response.read().split('\n')
            if data[0] == '':
                self.weather = -1
                return -1
            
            # convert the date into a datetime object
            weather = {
                'date':datetime.datetime.strptime(data[0],'%Y, %m, %d, %H, %M, %S, %f')}
            
            # populate the weather dictionary from the webpage
            for parameter in data[1:-1]:
                weather[(parameter.split('='))[0]] = float((parameter.split('='))[1])

            # add in the cloud monitor
            url = "http://mearth.sao.arizona.edu/weather/now"

            # read the webpage
            self.logger.debug('Requesting URL: ' + url)
            request = urllib2.Request(url)
            try:
                response = urllib2.urlopen(request)
            except:
                self.logger.error('Error reading the weather page: ' + str(sys.exc_info()[0]))
                site.weather = -1
                return
            data = response.read().split()
            if data[0] == '':
                self.logger.error('Error reading the weather page (empty response)')
                site.weather = -1
                return    
            if len(data) <> 14:
                self.logger.error('Error reading the weather page; response: ' + str(data))
                site.weather = -1
                return

            # MJD to datetime
            weather['cloudDate'] = datetime.datetime(1858,11,17,0) + datetime.timedelta(days=float(data[0]))
            weather['relativeSkyTemp'] = float(data[13])
            
        elif self.name == 'Pasadena':

            mainIP = '192.168.1.2' # Mt. Hopkins
            mainIP = '131.215.123.204' # Pasadena
            ssh = SSHClient()
            ssh.set_missing_host_key_policy(AutoAddPolicy())
            ssh.load_system_host_keys()
            ssh.connect(mainIP,port=22222,username='minerva',password='!bfthg&*9')

            scp = SCPClient(ssh.get_transport())
            try:
                scp.get('/home/minerva/Software/Status/weather_status','./')
            except:
                self.logger.error('Error SCPing the weather status')
                site.weather = -1
                return
            

            with open('weather_status','r') as f:
                data = f.readline().split()

            if len(data) <> 20:
                self.logger.error('Error reading the weather page; response: ' + str(data))
                site.weather = -1
                return

            weather = {}
            weather['date'] = datetime.datetime(1970,1,1) + datetime.timedelta(seconds=float(data[0]))
            weather['cloudDate'] = datetime.datetime(1970,1,1) + datetime.timedelta(seconds=float(data[0]))
            weather['outsideTemp'] = float(data[6])
            weather['windSpeed'] = float(data[8]) # km/hr (convert to mph?)
            weather['outsideHumidity'] = float(data[10])
            weather['outsideDewPt'] = float(data[12])

            # wetnes (0=unknown, 1=dry, 2=wet on sensor, 3=rain detected
            if data[14] <> '1': weather['wxt510Rain'] = 1.0
            else: weather['wxt510Rain'] = 0.0

            # clouds (0=Unknown, 1=clear, 2=cloudy, 3=very cloudy)
            if data[16] <> '1': weather['relativeSkyTemp'] = 999
            else: weather['relativeSkyTemp'] = -999
            
            # our weather station doesn't have these -- set to defaults within limits
            weather['totalRain'] = 0.0
            weather['barometer'] = 1000.0
            weather['windGustSpeed'] = 0.0
            weather['windDirectionDegrees'] = 0.0           
        elif self.name == 'Simulate' or self.name == 'Wellington':
            # get values that pass through
            weather = {}
            weather['date'] = datetime.datetime.utcnow()
            weather['cloudDate'] = datetime.datetime.utcnow()
            weather['outsideTemp'] = 20.0
            weather['windSpeed'] = 0.0
            weather['outsideHumidity'] = 0.0
            weather['outsideDewPt'] = 0.0
            weather['wxt510Rain'] = 0.0
            weather['relativeSkyTemp'] = 999
            weather['totalRain'] = 0.0
            weather['barometer'] = 1000.0
            weather['windGustSpeed'] = 0.0
            weather['windDirectionDegrees'] = 0.0
            
        # add in the Sun Altitude
        weather['sunAltitude'] = self.sunalt()
        
        # make sure all required keys are present
        pageError = False
        requiredKeys = ['totalRain', 'wxt510Rain', 'barometer', 'windGustSpeed', 
                        'outsideHumidity', 'outsideDewPt', 'outsideTemp', 
                        'windSpeed', 'windDirectionDegrees', 'date', 'sunAltitude',
                        'cloudDate', 'relativeSkyTemp']
        
        for key in requiredKeys:
            if not key in weather.keys():
                # if not, return an error
                self.logger.warning('Weather page does not have all required keys (' + key + ')')
                self.weather = -1
                pageError = True

        # if everything checks out, store the weather
        if not pageError: self.weather = weather

    def oktoopen(self, open=False):

        retval = True
        
        if open: weatherLimits = self.closeLimits
        else: weatherLimits = self.openLimits

        if self.sunOverride: weatherLimits['sunAltitude'] = [-90,90]
        if self.cloudOverride: weatherLimits['relativeSkyTemp'] = [-999,999]

        # get the current weather, timestamp, and Sun's position
        self.getWeather()
        while self.weather == -1:
            time.sleep(1)
            self.getWeather()

        # make sure each parameter is within the limits for safe observing
        for key in weatherLimits:
            if self.weather[key] < weatherLimits[key][0] or self.weather[key] > weatherLimits[key][1]:
                keyname = key
                if keyname == 'relativeSkyTemp': keyname = 'Clouds'
                self.logger.info('Not OK to open: ' + keyname + '=' + str(self.weather[key]) + '; Limits are ' + str(weatherLimits[key][0]) + ',' + str(weatherLimits[key][1]))
                retval = False

        if retval: self.logger.debug('OK to open')
        return retval

    def sunrise(self, horizon=0):

        self.obs.horizon = str(horizon)
        sunrise = self.obs.next_rising(ephem.Sun(), start=self.startNightTime, use_center=True).datetime()
        return sunrise
    
    def sunset(self, horizon=0):

        self.obs.horizon = str(horizon)
        sunset = self.obs.next_setting(ephem.Sun(), start=self.startNightTime, use_center=True).datetime()
        return sunset

    def NautTwilBegin(self, horizon=-12):

        self.obs.horizon = str(horizon)
        NautTwilBegin = self.obs.next_rising(ephem.Sun(), start=self.startNightTime, use_center=True).datetime()
        return NautTwilBegin
    
    def NautTwilEnd(self, horizon=-12):

        self.obs.horizon = str(horizon)
        NautTwilEnd = self.obs.next_setting(ephem.Sun(), start=self.startNightTime, use_center=True).datetime()
        return NautTwilEnd

    def sunalt(self):

        self.obs.date = datetime.datetime.utcnow()
        sun = ephem.Sun()
        sun.compute(self.obs)
        return float(sun.alt)*180.0/math.pi

    def sunaz(self):

        self.obs.date = datetime.datetime.utcnow()
        sun = ephem.Sun()
        sun.compute(self.obs)
        return float(sun.az)*180.0/math.pi

    def moonpos(self):
        moon = ephem.Moon()
        moon.compute(datetime.datetime.utcnow())
        moonpos = (moon.ra,moon.dec)
        return moonpos
    
    def moonphase(self):
        moon = ephem.Moon()
        moon.compute(datetime.datetime.utcnow())
        moonphase = moon.phase/100.0
        return moonphase

if __name__ == '__main__':
    flwo = site('Mount_Hopkins','n20150511',configfile='minerva_class_files/site.ini')
    ipdb.set_trace()
