from configobj import ConfigObj
import datetime, logging
import ephem, time

class site:

    def __init__(self,site_name, configfile=''):

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
        self.observing = True
        self.weather = -1
        
        # make these more dyamic (read from file?)
        self.cloudOverride = False 
        self.sunOverride = False

        logger_name = siteconfig['Setup']['LOGNAME']
        log_file = siteconfig['Setup']['LOGFILE']

        # reset the night at 10 am local
        today = datetime.datetime.utcnow()
        if datetime.datetime.now().hour > 10 and datetime.datetime.now().hour < 17:
            today = today + datetime.timedelta(days=1)
        self.night = 'n' + today.strftime('%Y%m%d')
        self.startNightTime = datetime.datetime(today.year, today.month, today.day, 17) - datetime.timedelta(days=1)

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
            'lastClose':[datetime.datetime(2000,1,1),datetime.datetime.utcnow()-datetime.timedelta(minutes=20)],
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
            'lastClose':[datetime.datetime(2000,1,1),datetime.datetime(2200,1,1)],
            }
        
	# setting up site logger
	self.logger = logging.getLogger(logger_name)
        formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
	fileHandler = logging.FileHandler(log_file, mode='w')
	fileHandler.setFormatter(formatter)
	streamHandler = logging.StreamHandler()
	streamHandler.setFormatter(formatter)

	self.logger.setLevel(logging.DEBUG)
	self.logger.addHandler(fileHandler)
	self.logger.addHandler(streamHandler)

    def getWeather(self):

        if self.name == 'Mount_Hopkins':
            # the URL for the machine readable weather page for the Ridge
            url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"

            # read the webpage
            self.logger.info('Requesting URL: ' + url)
            request = urllib2.Request(url)
            try:
                response = urllib2.urlopen(request)
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

            # add in the Sun Altitude
            weather['sunAltitude'] = sunAltitude()

            # add in the cloud monitor
            url = "http://mearth.sao.arizona.edu/weather/now"

            # read the webpage
            self.logger.info('Requesting URL: ' + url)
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
           
            # make sure all required keys are present
            pageError = False
            requiredKeys = ['totalRain', 'wxt510Rain', 'barometer', 'windGustSpeed', 
                            'outsideHumidity', 'outsideDewPt', 'outsideTemp', 
                            'windSpeed', 'windDirectionDegrees', 'date', 'sunAltitude',
                            'cloudDate', 'relativeSkyTemp']
            
            for key in requiredKeys:
                if not key in weather.keys():
                    # if not, return an error
                    logging.error('Weather page does not have all required keys (' + key + ')')
                    site.weather = -1
                    pageError = True

            # if everything checks out, store the weather
            if not pageError: self.weather = weather
            
        elif self.name == 'Pasadena':
            return -1

    def oktoopen(self, open=False):
        
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
                self.logger.info('Not OK to open: ' + key + '=' + str(self.weather[key]) + '; Limits are ' + str(weatherLimits[key][0]) + ',' + str(weatherLimits[key][1]))
                retval = False

        return retval

    def sunrise(self, horizon=-12):

        self.obs.horizon = str(horizon)
        sun = ephem.Sun()
        sunrise = obs.next_rising(sun, start=self.startNightTime, use_center=True).datetime()
        return sunrise
    
    def sunset(self, horizon=-12):

        self.obs.horizon = str(horizon)
        sun = ephem.Sun()
        sunset = obs.next_setting(sun, start=self.startNightTime, use_center=True).datetime()
        return sunset

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
