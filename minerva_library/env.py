import datetime
import logging
import ephem
import time
import math 
import os
import sys
import urllib2
from configobj import ConfigObj
sys.dont_write_bytecode = True

class site:

	def __init__(self,config, base):

		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.setup_logger()
		
	def load_config(self):
	
		try:
			config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.latitude = config['Setup']['LATITUDE']
			self.longitude = config['Setup']['LONGITUDE']        
			self.elevation = float(config['Setup']['ELEVATION'])
			self.logger_name = config['Setup']['LOGNAME']
			# touch a file in the current directory to enable cloud override
			self.cloudOverride = os.path.isfile('cloudOverride.txt') 
			self.sunOverride = os.path.isfile('sunOverride.txt')
			
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()
		
		self.observing = True
		self.weather = -1
		self.rainChangeDate = datetime.datetime.utcnow() - datetime.timedelta(hours=1.0)
		self.lastRain = 0.0

		# reset the night at 10 am local
		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
			today = today + datetime.timedelta(days=1)
		self.night = 'n' + today.strftime('%Y%m%d')
		self.startNightTime = datetime.datetime(today.year, today.month, today.day, 17) - datetime.timedelta(days=1)

		self.lastClose = datetime.datetime.utcnow() - datetime.timedelta(days=1)

		self.obs = ephem.Observer()
		self.obs.lat = ephem.degrees(str(self.latitude)) # N
		self.obs.lon = ephem.degrees(str(self.longitude)) # E
		self.obs.elevation = self.elevation # meters

		# define more conservative limits to open to prevent cycling when borderline conditions
		#TODO Revert wxtrain
		self.openLimits = {
			'totalRain':[0.0,1000.0],
			'wxt510Rain':[0.0,50.0], 
			'barometer':[0,2000], 
			'windGustSpeed':[0.0,35.0], 
			'outsideHumidity':[0.0,75.0], 
			'outsideDewPt':[-100.0,100.0],
			'outsideTemp':[-20.0,50.0], 
			'windSpeed':[0.0,30.0], 
			'windDirectionDegrees':[0.0,360.0],
			'date':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
			'sunAltitude':[-90,0],
			'MearthCloud':[-999,-30],
			'HATCloud': [-999,-999],			
			'AuroraCloud': [-999,-999],
			'cloudDate':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)]
			}

		self.closeLimits = {
			'totalRain':[0.0,1000.0],
			'wxt510Rain':[0.0,50.0], 
			'barometer':[0,2000], 
			'windGustSpeed':[0.0,40.0], 
			'outsideHumidity':[0.0,80.0], 
			'outsideDewPt':[-100.0,100.0],
			'outsideTemp':[-30.0,60.0], 
			'windSpeed':[0.0,35.0], 
			'windDirectionDegrees':[0.0,360.0],
			'date':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
			'sunAltitude':[-90,0],
			'MearthCloud':[-999,-28],
			'HATCloud': [-999,-999],			
			'AuroraCloud': [-999,-999],
			'cloudDate':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)]
			}
			
	def setup_logger(self):
			
		log_path = self.base_directory + '/log/' + self.night
		if os.path.exists(log_path) == False:os.mkdir(log_path)
		
                # setting up aqawan logger                                                                                            
                fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
                datefmt = "%Y-%m-%dT%H:%M:%S"

                self.logger = logging.getLogger(self.logger_name)
                self.logger.setLevel(logging.DEBUG)
                formatter = logging.Formatter(fmt,datefmt=datefmt)
                formatter.converter = time.gmtime

                #clear handlers before setting new ones                                                                               
                self.logger.handlers = []

                fileHandler = logging.FileHandler(log_path + '/' + self.logger_name + '.log', mode='a')
                fileHandler.setFormatter(formatter)
                self.logger.addHandler(fileHandler)

                # add a separate logger for the terminal (don't display debug-level messages)                                         
                console = logging.StreamHandler()
                console.setFormatter(formatter)
                console.setLevel(logging.INFO)
                self.logger.setLevel(logging.DEBUG)
                self.logger.addHandler(console)

	def getWeather(self):

		if self.logger_name == 'site_mtHopkins':
			# the URL for the machine readable weather page for the Ridge
			url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"

			# read the webpage
			self.logger.debug('Requesting URL: ' + url)
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



			'''
			#S Acquire readings from the three cloud monitors at the address below. Order at 
			#S website is Date, Mearth, HAT, Aurora.
			url = 'http://linmax.sao.arizona.edu/temps/sky_temps'
			#S Try everything, but if anyhting fails we really want to stay closed.
			try: 
				#S Read the last line from the url above, and split it at the spaces.
				cloudstr = os.popen('curl -s ' + url + ' | tail -1').read().split(' ')
				#S Get the date from the line by concatenating the first split, then adding 7:00:00 to put in UTC.
				weather['cloudDate'] = datetime.datetime.strptime(cloudstr[0]+' '+cloudstr[1],'%b-%d-%Y %H:%M:%S') + datetime.timedelta(hours=7)
				#S Assign as specified.

				weather['MearthCloud'] = float(cloudstr[2])
				weather['HATCloud'] = float(cloudstr[3])
				weather['AuroraCloud'] = float(cloudstr[4])
			except: 
				self.weather = -1
				pageError = True
				
#				self.logger.error('Error reading the page for cloud temps at '+url)
#				#S We'll set everything to close essentially, and make cloudDate utcnow.
#				weather['cloudDate'] = datetime.datetime.utcnow()
#				weather['MearthCloud'] = 999
#				weather['HATCloud'] = 999
#				weather['AuroraCloud'] = 999
'''

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
				return -1
			data = response.read().split()
			if data[0] == '':
				self.logger.error('Error reading the weather page (empty response)')
				site.weather = -1
				return -1
			if len(data) <> 14:
				self.logger.error('Error reading the weather page; response: ' + str(data))
				site.weather = -1
				return -1

			# MJD to datetime
			weather['cloudDate'] = datetime.datetime(1858,11,17,0) + datetime.timedelta(days=float(data[0]))
			weather['MearthCloud'] = float(data[13])
			weather['HATCloud'] = 999
			weather['AuroraCloud'] = 999
			
		elif self.logger_name == 'site_Simulate' or self.logger_name == 'site_Wellington':
                        # get values that pass through
                        weather = {}
                        weather['date'] = datetime.datetime.utcnow()
                        weather['cloudDate'] = datetime.datetime.utcnow()
                        weather['outsideTemp'] = 20.0
                        weather['windSpeed'] = 0.0
                        weather['outsideHumidity'] = 0.0
                        weather['outsideDewPt'] = 0.0
                        weather['wxt510Rain'] = 0.0
                        weather['MearthCloud'] = 999
                        weather['AuroraCloud'] = 999
                        weather['HATCloud'] = 999
                        weather['totalRain'] = 0.0
                        weather['barometer'] = 1000.0
                        weather['windGustSpeed'] = 0.0
                        weather['windDirectionDegrees'] = 0.0
			
		# add in the Sun Altitude
		weather['sunAltitude'] = self.sunalt()
		
		# make sure all required keys are present
                #S Do we want to require other cloud monitors?
		#TODO See above
		pageError = False
		requiredKeys = ['totalRain', 'wxt510Rain', 'barometer', 'windGustSpeed', 
                                'outsideHumidity', 'outsideDewPt', 'outsideTemp', 
				'windSpeed', 'windDirectionDegrees', 'date', 'sunAltitude',
				'cloudDate', 'MearthCloud', 'HATCloud', 'AuroraCloud']
		
		for key in requiredKeys:
			if not key in weather.keys():
				# if not, return an error
				logging.error('Weather page does not have all required keys (' + key + ')')
				self.weather = -1
				pageError = True

		# if everything checks out, store the weather
		if not pageError: self.weather = weather

		# write the weather to the log for nightly summaries
		for key in weather.keys():
			self.logger.debug(key + '=' + str(weather[key]))

	def oktoopen(self, open=False):
		
		retval = True

		# if it's open, use the limits to close
		if open:
			self.logger.debug("Enclosure open; using the close limits")
			weatherLimits = self.closeLimits
		else:
			self.logger.debug("Enclosure closed; using the open limits")
			weatherLimits = self.openLimits
			
		# change it during execution
		if os.path.exists('sunOverride.txt'): self.sunOverride = True
		if os.path.exists('cloudOverride.txt'): self.cloudOverride = True

		if self.sunOverride: weatherLimits['sunAltitude'] = [-90,90]
		if self.cloudOverride: 
			weatherLimits['MearthCloud'] = [-999,999]
			weatherLimits['HATCloud'] = [-999,999]
			weatherLimits['AuroraCloud'] = [-999,999]

		# get the current weather, timestamp, and Sun's position
		self.getWeather()
		while self.weather == -1:
			time.sleep(1)
			self.getWeather()


		if self.weather['wxt510Rain'] > self.lastRain:
			self.lastRain = self.weather['wxt510Rain']
			self.rainChangeDate = datetime.datetime.utcnow()

		# if it has rained in the last hour, it's not ok to open
		if (datetime.datetime.utcnow() - self.rainChangeDate).total_seconds() < 3600.0:
			self.logger.info('Not OK to open: it last rained at ' + str(self.rainChangeDate) + ", which is less than 1 hour ago")
			retval = False

		#S External temperature check, want to use Mearth, then Aurora if Mearth not available, and then 
		#S HAT if niether of those two are found. Currently, we are assuming a value of 0 means disconnected
		#S for any of the three sensors.
		if self.weather['MearthCloud'] <> 0:
			key = 'MearthCloud'
			if self.weather[key] < weatherLimits[key][0] or self.weather[key] > weatherLimits[key][1]:
				self.logger.info('Not OK to open: ' + key + '=' + str(self.weather[key]) + '; Limits are ' + str(weatherLimits[key][0]) + ',' + str(weatherLimits[key][1]))
				retval = False
		elif self.weather['AuroraCloud'] <> 0:
			key = 'AuroraCloud'
			if self.weather[key] < weatherLimits[key][0] or self.weather[key] > weatherLimits[key][1]:
				self.logger.info('Not OK to open: ' + key + '=' + str(self.weather[key]) + '; Limits are ' + str(weatherLimits[key][0]) + ',' + str(weatherLimits[key][1]))
				retval = False
		elif self.weather['HATCloud'] <> 0:
			key = 'HATCloud'
			if self.weather[key] < weatherLimits[key][0] or self.weather[key] > weatherLimits[key][1]:
				self.logger.info('Not OK to open: ' + key + '=' + str(self.weather[key]) + '; Limits are ' + str(weatherLimits[key][0]) + ',' + str(weatherLimits[key][1]))
				retval = False
		else:
			self.logger.info('Not OK to open: all cloud sensors down')
			retval = False

		# make sure each parameter is within the limits for safe observing
		for key in weatherLimits:
			if 'Cloud' not in key and (self.weather[key] < weatherLimits[key][0] or self.weather[key] > weatherLimits[key][1]):
				keyname = key
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
		
	def NautTwilBegin(self, horizon=-8):

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

	base_directory = '/home/minerva/minerva-control'
	test_site = site('site_mtHopkins.ini',base_directory)
	print test_site.night
	print test_site.oktoopen()
	
	
	
