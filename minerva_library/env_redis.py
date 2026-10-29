import matplotlib
matplotlib.use('Agg',warn=False)
import redis
import datetime
import logging
import ephem
import time
import math
import os
import sys
import matplotlib.pyplot as plt
import numpy as np
import urllib2
from configobj import ConfigObj
sys.dont_write_bytecode = True
import ipdb
import mail
import threading
import copy
import utils
from weather_thach import get_current_weather
from astropy.time import Time
import requests

class site:

	def __init__(self,config, base):

		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
		self.lock = threading.Lock()

	def load_config(self):

		try:
			config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.latitude = config['Setup']['LATITUDE']
			self.longitude = config['Setup']['LONGITUDE']
			self.elevation = float(config['Setup']['ELEVATION'])
			self.logger_name = config['Setup']['LOGNAME']
			# touch a file in the current directory to enable cloud override
			self.cloudOverride = False
			self.sunOverride = False
			self.timeoutOverride = False
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()

		self.observing = True
		self.weather = -1
		self.rainChangeDate = datetime.datetime.utcnow() - datetime.timedelta(hours=25.0)
		self.lastRain = 0.0
		self.mailSent = False
		self.coldestTemp = 100.0

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


		# the cloud sensors have an uncalibrated offset and scale
		# apply these externally calibrated scaling factors to the limits
		cloudScale = {
			'mearth'  : (1.00000000,0.000000000),
			'aurora'  : (0.89876588,6.878974400),
			'hat'     : (0.98378265,1.289965700),
			'minerva' : (0.74102145,0.058437186)
#			'minerva' : (1.34948860,0.058437186)
			}
		openCloudLimit = -30
		closeCloudLimit = -28


		self.openLimits = {
			'totalRain'           : [0.0,999999.0],

			'wxt510Rain'          : [0.0,99999.0],
			'barometer'           : [0,2000],
			'windGustSpeed'       : [0.0,35.0],
	#		'windGustSpeed'       : [0.0,999.0],
			'outsideHumidity'     : [0.0,75.0],
			'outsideDewPt'        : [-100.0,100.0],
			'outsideTemp'         : [-20.0,50.0],
			'windSpeed'           : [0.0,30.0],
			'windDirectionDegrees': [0.0,360.0],
			'date'                : [datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
			'sunAltitude'         : [-90,15],
#			'MearthCloud'         : [-999, 999],
			'MearthCloud'         : [-999, openCloudLimit*cloudScale['mearth'][0] +cloudScale['mearth'][1]],
			'HATCloud'            : [-999, openCloudLimit*cloudScale['hat'][0] +cloudScale['hat'][1]],
			#'AuroraCloud'         : [-999, openCloudLimit*cloudScale['aurora'][0]    +cloudScale['aurora'][1]],
			'AuroraCloud'         : [-999, -32],
			'MINERVACloud'        : [-999, openCloudLimit*cloudScale['minerva'][0]+cloudScale['minerva'][1]],
			'cloudDate'           : [datetime.datetime.utcnow()-datetime.timedelta(minutes=6),datetime.datetime(2200,1,1)]
			}

		self.closeLimits = {
			'totalRain'           : [0.0,100000.0],
#			'wxt510Rain'          : [0.0,50.0],		   
			'wxt510Rain'          : [0.0, 99999.0],
			'barometer'           : [0,2000],
			'windGustSpeed'       : [0.0,40.0],
	#		'windGustSpeed'       : [0.0,999.0],
			'outsideHumidity'     : [0.0,80.0],
			'outsideDewPt'        : [-100.0,100.0],
			'outsideTemp'         : [-30.0,60.0],
			'windSpeed'           : [0.0,35.0],
			'windDirectionDegrees': [0.0,360.0],
			'date'                : [datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
			'sunAltitude'         : [-90,15],
#			'MearthCloud'         : [-999, 999],
			'MearthCloud'         : [-999, closeCloudLimit*cloudScale['mearth'][0] +cloudScale['mearth'][1]],
			'HATCloud'            : [-999, closeCloudLimit*cloudScale['hat'][0] +cloudScale['hat'][1]],
#			'AuroraCloud'         : [-999, closeCloudLimit*cloudScale['aurora'][0]    +cloudScale['aurora'][1]],
			'AuroraCloud'         : [-999, -31],
			'MINERVACloud'        : [-999, closeCloudLimit*cloudScale['minerva'][0]+cloudScale['minerva'][1]],
			'cloudDate'           : [datetime.datetime.utcnow()-datetime.timedelta(minutes=6),datetime.datetime(2200,1,1)]
			}

	def getWeatherMearth(self):

		url = "http://mearth.sao.arizona.edu/weather/now"

		# read the webpage
		self.logger.debug('Requesting URL: ' + url)
		request = urllib2.Request(url)
		try:
			response = urllib2.urlopen(request)
		except:
			self.logger.error('Error reading the weather page: ' + str(sys.exc_info()[0]))
			return {}
		
		data = response.read().split()

		if len(data) != 15: return {}

		# TODO: update astropy to get rid of dubious year?
#		mjd = Time(float(data[0]), format='mjd')
#		date2 = mjd.datetime

		# convert mjd to datetime object
		jd = float(data[0]) + 2400000.5
		date = utils.jd2datetime(jd)
		now = datetime.datetime.utcnow()

		if date < (now - datetime.timedelta(minutes=10)):
			return {}

		try:
			weather = {'date':date, 
				   'outsideTemp':float(data[3]), # C
				   'windSpeed':float(data[2]), #km/h
				   'windGustSpeed':float(data[14]),# (km/h?)
				   'windDirectionDegrees':float(data[1]), # degrees (I assume)
				   'barometer':float(data[6]) * 1.33322,  # mmHg ->  hPa
				   'outsideHumidity':float(data[5]), # % (I assume)
				   'wxt510Rain':float(data[9]), # mm
				   'totalRain':0.0,
				   'outsideDewPt':float(data[4]), # C (I assume)
				   'rainDuration':float(data[8]), # seconds
				   'rainIntensity':float(data[9]), # mm/hr
				   'hailAccumulation':float(data[10]), # mm
				   'hailDuration':float(data[11]), # seconds
				   'hailIntensity':float(data[12]), # mm/hr
				   'skyTemp':float(data[13]) # mm/hr
				   }
		except:
			return {}
		return weather

	def getWeatherRidge(self):
		# the URL for the machine readable weather page for the Ridge
		url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"


		

		# read the webpage
		self.logger.debug('Requesting URL: ' + url)
#		request = urllib2.Request(url)
		try:
			f = open(self.base_directory + '/credentials/webpage.txt')
			username = f.readline().strip()
			password = f.readline().strip()
			f.close()
			response = requests.get(url,auth=(username,password)).text
			data = response.split('\n')
#			response = urllib2.urlopen(request)#
#			data = response.read().split('\n')
		except:
			self.logger.error('Error reading the weather page: ' + str(sys.exc_info()[0]))
			return {}


		if data[0] == '':
			self.logger.error('Error reading the weather page: ' + str(sys.exc_info()[0]))
			return {}

		# convert the date into a datetime object
		try:
			weather = {
				'date':datetime.datetime.strptime(data[0],'%Y, %m, %d, %H, %M, %S, %f')}
		except:
			self.logger.error('Error reading the weather page: ' + str(sys.exc_info()[0]))
			return {}

		# populate the weather dictionary from the webpage
		for parameter in data[1:-1]:
			weather[(parameter.split('='))[0]] = float((parameter.split('='))[1])
		return weather


	def getWeather(self):

           self.logger.debug("Beginning serial communications with the weather station")
	   pageError = False
           with self.lock:

		if self.logger_name == 'site_mtHopkins':

			# use MEarth weather station, backup of Ridge weather station
			weather = self.getWeatherMearth()
			if len(weather) == 0:
				self.logger.warning("MEarth weather failed. Getting weather from ridge sensor.")
				weather = self.getWeatherRidge()

			#S Acquire readings from the three cloud monitors at the address below. Order at
			#S website is Date, Mearth, HAT, Aurora, MINERVA.
			# this has a reading every 5 minutes since September 2014
			url = 'http://linmax.sao.arizona.edu/temps/sky_temps_now'
			#S Try everything, but if anyhting fails we really want to stay closed.
			try:
				#S Read the last line from the url above, and split it at the spaces.
#				cloudstr = os.popen('curl -s ' + url).read().split(' ')
				f = open(self.base_directory + '/credentials/webpage.txt')
				username = f.readline().strip()
				password = f.readline().strip()
				f.close()
				cloudstr = requests.get(url,auth=(username,password)).text.split()

				if len(cloudstr) == 6:
				        #S Get the date from the line by concatenating the first split, then add 7 hours to put in UTC.
					weather['cloudDate'] = datetime.datetime.strptime(" ".join(cloudstr[0:2]),'%b-%d-%Y %H:%M:%S') + datetime.timedelta(hours=7)
					#S Assign as specified.
					# if the connection is lost, it returns 0
					weather['MearthCloud'] = float(cloudstr[2])
					if weather['MearthCloud'] == 0.0: weather['MearthCloud'] = 999
					weather['HATCloud'] = float(cloudstr[3])
					if weather['HATCloud'] == 0.0: weather['HATCloud'] = 999
					weather['AuroraCloud'] = float(cloudstr[4])
					if weather['AuroraCloud'] == 0.0: weather['AuroraCloud'] = 999
					weather['MINERVACloud'] = float(cloudstr[5])
					if weather['MINERVACloud'] == 0.0: weather['MINERVACloud'] = 999
				elif len(cloudstr) == 4:
				        #S Get the date from the line by concatenating the first split, then add 7 hours to put in UTC.
					weather['cloudDate'] = datetime.datetime.strptime(" ".join(cloudstr[0:2]),'%b-%d-%Y %H:%M:%S') + datetime.timedelta(hours=7)
					#S Assign as specified.
					# if the connection is lost, it returns 0
					weather['MearthCloud'] = float(cloudstr[2])
					if weather['MearthCloud'] == 0.0: weather['MearthCloud'] = 999
					weather['AuroraCloud'] = float(cloudstr[3])
					if weather['AuroraCloud'] == 0.0: weather['AuroraCloud'] = 999
					weather['HATCloud'] = 999
					weather['MINERVACloud'] = 999					
					weather['MearthCloud']=999 # MEarth disabled as of 2022-02-03
				else:
					self.logger.error("Error reading the cloud page; line is: " + " ".join(cloudstr))

			except:
				# error reading the cloud monitor, don't update the values
				self.logger.error('Error reading the page for cloud temps at '+url)
				pageError = True

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
                        weather['MINERVACloud'] = 999
                        weather['totalRain'] = 0.0
                        weather['barometer'] = 1000.0
                        weather['windGustSpeed'] = 0.0
                        weather['windDirectionDegrees'] = 0.0

		elif self.logger_name == 'site_Thach':
			weather = get_current_weather()
			weather['barometer'] = 1000 #TODO: check if have
			weather['windDirectionDegrees'] = 0.

		# add in the Sun Altitude
		weather['sunAltitude'] = self.sunalt()

		# make sure all required keys are present
		requiredKeys = ['totalRain', 'wxt510Rain', 'barometer', 'windGustSpeed',
                                'outsideHumidity', 'outsideDewPt', 'outsideTemp',
				'windSpeed', 'windDirectionDegrees', 'date', 'sunAltitude',
				'cloudDate', 'MearthCloud', 'HATCloud', 'AuroraCloud', 'MINERVACloud']

		for key in requiredKeys:
			if not key in weather.keys():
				# if not, return an error
				logging.error('Weather page does not have all required keys (' + key + ')')
				pageError = True

		# if everything checks out, store the weather
		if not pageError: self.weather = copy.deepcopy(weather)

		# record the coldest temp for snow/ice detection
		try:
			if self.weather['outsideTemp'] < self.coldestTemp:
				self.coldestTemp = weather['outsideTemp']
		except: pass

		# write the weather to the log for nightly summaries
		for key in weather.keys():
			self.logger.debug(key + '=' + str(weather[key]))

	def oktoopen(self, domeid, domeopen=False, ignoreSun=False):

		retval = True
		decisionFile = self.base_directory + '/manualDecision.txt'

		# get the current weather, timestamp, and Sun's position
		self.getWeather()
		while self.weather == -1:
			time.sleep(1)
			self.getWeather()

		# conditions have necessitated a manual decision to open the domes
		if os.path.exists(decisionFile):
			f = open(decisionFile,'r')
			try: date = datetime.datetime.strptime(f.readline().strip(),'%Y-%m-%d %H:%M:%S.%f')
			except: date = datetime.datetime.utcnow() - datetime.timedelta(days=1.1)
			f.close()

			if (datetime.datetime.utcnow() - date).total_seconds() > 86400.0:
				if not self.mailSent:
					mail.send("Possible snow/ice on enclosures; manual inspection required",
						  "Dear benevolent humans,\n\n"+
						  "Recent conditions have been wet and cold (" + str(self.coldestTemp) + " C), which means ice and/or snow is likely. "+
						  "I have disabled operations until someone can check the camera (http://minervacam.sao.arizona.edu) "+
						  "to ensure there is no snow or ice on the roof and the snow is not more than 2 inches deep "+
						  "(which will stall the roof. There are presets on the camera for 'A1 Snow line' and 'A2 Snow line'. The you must "+
						  "be able to see the red line below the black line for it to be safe to open. If the snow on the ground "+
						  "is too deep, please email the site staff to ask them to shovel.\n\n"+
						  "If everything looks good, either delete the '/home/minerva/minerva-control/manualDecision.txt' file "+
						  "(if current conditions will not trip this warning again) or edit the date in that file to UTC now (" +
						  str(datetime.datetime.utcnow()) + "). Note that this warning will be tripped again 24 hours after the "+
						  "date in that file.\n\n"
						  "Love,\nMINERVA",level='serious')
					self.mailSent = True
				self.logger.info("Not OK to open -- manual decision required")
				return False
		if self.mailSent:
			mail.send("Snow/ice conditions have been manually checked and OK'ed",
				  "Resuming normal operations",level='serious')
			self.mailSent = False

		# if it's open, use the limits to close
		if domeopen:
			self.logger.debug("Enclosure open; using the close limits")
			weatherLimits = copy.deepcopy(self.closeLimits)
		else:
			self.logger.debug("Enclosure closed; using the open limits")
			weatherLimits = copy.deepcopy(self.openLimits)

		# change it during execution
		self.sunOverride = os.path.exists(self.base_directory + '/minerva_library/sunOverride.' + domeid + '.txt') or ignoreSun
		self.cloudOverride = os.path.exists(self.base_directory + '/minerva_library/cloudOverride.' + domeid + '.txt')
		self.timeoutOverride = os.path.exists(self.base_directory + '/minerva_library/timeoutOverride.' + domeid + '.txt')

		if self.sunOverride: weatherLimits['sunAltitude'] = [-90,90]
		else: weatherLimits['sunAltitude'] = [-90,6]

		if self.cloudOverride:
			weatherLimits['MearthCloud'] = [-999,999]
			weatherLimits['HATCloud'] = [-999,999]
			weatherLimits['AuroraCloud'] = [-999,999]
			weatherLimits['MINERVACloud'] = [-999,999]
		else:
			if domeopen:
				weatherLimits['MearthCloud'] = self.closeLimits['MearthCloud']
				weatherLimits['HATCloud'] = self.closeLimits['HATCloud']
				weatherLimits['AuroraCloud'] = self.closeLimits['AuroraCloud']
				weatherLimits['MINERVACloud'] = self.closeLimits['MINERVACloud']
			else:
				weatherLimits['MearthCloud'] = self.openLimits['MearthCloud']
				weatherLimits['HATCloud'] = self.openLimits['HATCloud']
				weatherLimits['AuroraCloud'] = self.openLimits['AuroraCloud']
				weatherLimits['MINERVACloud'] = self.openLimits['MINERVACloud']



		if weatherLimits['sunAltitude'][1] == 90:
			if not ignoreSun: self.logger.info("Sun override in place!")
		if self.closeLimits['sunAltitude'][1] == 90:
			self.logger.info("close limits have been modified; this shouldn't happen!")
		if self.openLimits['sunAltitude'][1] == 90:
			self.logger.info("open limits have been modified; this shouldn't happen!")

		# MearthCloud reports 998.0 when it's raining and is much more reliable than wxt510Rain
		#if self.weather['MearthCloud'] == 998.0:
		#	self.lastRain += 0.001
		#	self.rainChangeDate = datetime.datetime.utcnow()

		# wxt510Rain uses an impact sensor and can be triggered by wind (unreliable)
		if self.weather['wxt510Rain'] > self.lastRain:
			self.lastRain = self.weather['wxt510Rain']
			self.rainChangeDate = datetime.datetime.utcnow()

		# if it has rained in the last hour, it's not ok to open
		if (datetime.datetime.utcnow() - self.rainChangeDate).total_seconds() < 3600.0:
			self.logger.info('Not OK to open: it last rained at ' + str(self.rainChangeDate) + ", which is less than 1 hour ago")
			retval = False

		# if it has (or might have) snowed in the last 24 hours, we need manual approval to open
		if ((datetime.datetime.utcnow() - self.rainChangeDate).total_seconds() < 86400.0 and self.coldestTemp < 1.0) or os.path.exists(decisionFile):
			if os.path.exists(decisionFile):
				f = open(decisionFile,'r')
				date = datetime.datetime.strptime(f.readline().strip(),'%Y-%m-%d %H:%M:%S.%f')
				if (datetime.datetime.utcnow() - date).total_seconds() > 86400.0:
					with open(decisionFile,"w") as fh:
						fh.write(str(datetime.datetime.utcnow() - datetime.timedelta(days=1)))
						self.logger.info('Not OK to open: there has been precipitation in the last 24 hours and it has been freezing. Manual inspection for snow/ice required')
						return False
				else:
					self.logger.info('There has been precipitation in the last 24 hours and it has been freezing, but it has been manually approved to open until ' + str(date))

			else:
				with open(decisionFile,"w") as fh:
					fh.write(str(datetime.datetime.utcnow() - datetime.timedelta(days=1)))
					self.logger.info('Not OK to open: there has been precipitation in the last 24 hours and it has been freezing. Manual inspection for snow/ice required')
					return False

		#S External temperature check, want to use Mearth, then HAT if Mearth not available, and then
		#S Aurora, and finally MINERVA. Currently, we are assuming a value of 999 means disconnected
		#S for any of the four sensors.
		if self.weather['MearthCloud'] <> 999:
			key = 'MearthCloud'
			if self.weather[key] < weatherLimits[key][0] or self.weather[key] > weatherLimits[key][1]:
				self.logger.info('Not OK to open: ' + key + '=' + str(self.weather[key]) + '; Limits are ' + str(weatherLimits[key][0]) + ',' + str(weatherLimits[key][1]))
				retval = False
		elif self.weather['HATCloud'] <> 999:
			key = 'HATCloud'
			if self.weather[key] < weatherLimits[key][0] or self.weather[key] > weatherLimits[key][1]:
				self.logger.info('Not OK to open: ' + key + '=' + str(self.weather[key]) + '; Limits are ' + str(weatherLimits[key][0]) + ',' + str(weatherLimits[key][1]))
				retval = False
		elif self.weather['AuroraCloud'] <> 999:
			key = 'AuroraCloud'
			if self.weather[key] < weatherLimits[key][0] or self.weather[key] > weatherLimits[key][1]:
				self.logger.info('Not OK to open: ' + key + '=' + str(self.weather[key]) + '; Limits are ' + str(weatherLimits[key][0]) + ',' + str(weatherLimits[key][1]))
				retval = False
		elif self.weather['MINERVACloud'] <> 999:
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


	def sunrise(self, horizon=0, start=None):
		if start == None: start = self.startNightTime
		self.obs.horizon = str(horizon)
		sunrise = self.obs.next_rising(ephem.Sun(), start=start, use_center=True).datetime()
		return sunrise

	def sunset(self, horizon=0, start=None):
		if start == None: start = self.startNightTime
		self.obs.horizon = str(horizon)
		sunset = self.obs.next_setting(ephem.Sun(), start=start, use_center=True).datetime()
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
	test_site.getWeatherRidge()

	ipdb.set_trace()

	start = 'n20160101'
	end = 'n20191231'
	start_dt = datetime.datetime.strptime(start,'n%Y%m%d')
	end_dt = datetime.datetime.strptime(end,'n%Y%m%d')
	dates = [start_dt + datetime.timedelta(days=x) for x in range(0, (end_dt-start_dt).days+1)]


        nbias=11
	ndark=11
	nflat=11
	darkexptime=300
	flatexptime=1

	ro_time = 22
	b_time = nbias*ro_time
	d_time = ndark*(darkexptime+ro_time)
	sf_time = nflat*(flatexptime+ro_time)+120
	cal_time = (b_time+d_time+sf_time)/3600.

	nauttwils = []

	for today in dates:
		test_site.obs.date = today
		test_site.startNightTime = datetime.datetime(today.year, today.month, today.day, 17) - datetime.timedelta(days=1)
		nauttwils.append((test_site.NautTwilEnd()-today).total_seconds())
	nauttwils = np.array(nauttwils)/3600.
	print 'fewest minutes between cals and twil: '+str((np.min(nauttwils)-cal_time)*60.)
	plt.plot(nauttwils)
	plt.plot([0,len(nauttwils)],[cal_time,cal_time],'r')
	plt.plot([0,len(nauttwils)],[cal_time,cal_time],'r')
	plt.plot([0,len(nauttwils)],[0,0],'k')
	plt.show()


	ipdb.set_trace()
	print test_site.night
	print test_site.oktoopen()
