'''basic power switch control class, writes log to P(1 or 2).log file
create class object by powerswitch(num), where num specify which powerswitch
test program creates powerswitch(1) object and send keyboard commands'''

import sys
import os
import time
import urllib2
import ipdb
import datetime
import logging
import requests
from configobj import ConfigObj
from requests.auth import HTTPBasicAuth
sys.dont_write_bytecode = True
import utils

#To Do: change log to appropriate format, log open/close failure by reading status, add more functionality as needed 
class powerswitch:

	#powerswitch class init method, pass powerswitch_1.ini to powerswitch_5.ini
	def __init__(self, config, base):

		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
		
	def load_config(self):
			   
		try:
			configObj = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.IP = configObj['Setup']['IP']
			self.PORT = configObj['Setup']['PORT']
			self.logger_name = configObj['Setup']['LOGNAME']
			self.outlets = configObj['Setup']['OUTLETS']
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit() 

                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')

	def send(self,url):

		f = open(self.base_directory + '/credentials/authentication.txt','r')
		username = f.readline().strip()
		password = f.readline().strip()
		f.close()
		self.logger.info('Sending command: ' + url)
		response = requests.get(url,auth=(username, password))
		self.logger.info('Response code = ' + str(response.status_code))
		return response
	
	def on(self,outlet):
		url = 'http://' + self.IP + '/outlet?' + str(outlet) + '=ON'
		return self.send(url)

	def off(self,outlet):
		url = 'http://' + self.IP + '/outlet?' + str(outlet) + '=OFF'
		return self.send(url)
	
	def cycle(self,outlet,cycletime=None):

		if cycletime == None:
			url = 'http://' + self.IP + '/outlet?' + str(outlet) + '=CCL'
			return self.send(url)
		else:
			self.off(outlet)
			time.sleep(cycletime)
			return self.on(outlet)  

if __name__ == '__main__':

	config_file = 'powerswitch_1.ini'
	base_directory = '/home/minerva/minerva-control'
	p1 = powerswitch(config_file,base_directory)
	print p1.cycle(4)
	
	
	
	
	
	
	
	
	
	
	
	
