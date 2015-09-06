import sys
import time
import os
from optparse import OptionParser
import logging
import socket

#sys.path.insert (0, os.path.join (os.getcwd(), '..'))

#? What's going on here?
from si import __progname__, __description__, __copyleft__


from si.client import SIClient
from si.imager import Imager


class SI_imager:

	def __init__(self,name, base =''):

		self.name = name
		self.base_directory = base
		self.setup_logger()
		self.load_config()
		self.initialize()
		self.status_lock = threading.RLock()
		# threading.Thread(target=self.write_status_thread).start()

	#initialize 
	def initialize(self):

		client = SIClient (options.host, options.port)
		self.imager = Imager (client)
		
	def load_config(self):
	
		configfile = 'SI_imager.ini'
		try:
			config = ConfigObj(self.base_directory + '/config/' + configfile)[self.name]
			self.ip = config['Setup']['SERVER_IP']
			self.port = int(config['Setup']['SERVER_PORT'])
			
			self.platescale = float(config['Setup']['PLATESCALE'])
			self.filters = config['FILTERS']

		except:
			print('ERROR accessing ', self.name, ".", self.name, " was not found in the configuration file", configfile)
			return

	#set up logger object
	def setup_logger(self,night='dump'):
		log_path = self.base_directory + '/log/' + night
		if os.path.exists(log_path) == False:os.mkdir(log_path)
		
		self.logger = logging.getLogger(self.name)
		formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
		fileHandler = logging.FileHandler(log_path + '/' + self.name +'.log', mode='a')
		fileHandler.setFormatter(formatter)
		streamHandler = logging.StreamHandler()
		streamHandler.setFormatter(formatter)

		self.logger.setLevel(logging.DEBUG)
		self.logger.addHandler(fileHandler)
		self.logger.addHandler(streamHandler)
	#return a socket object connected to the camera server

	def test(self):
		try:
			self.imager.nexp = 1	#num of exposure
			self.imager.texp = 1.0	#time of exposure in seconds
			self.imager.nome = "image"	#name of the image to be saved (without index, only the basename)
			self.imager.dark = False	#Dark exposure (closed shutter).
			self.imager.frametransfer = False	#"Use frame transfer mode. See README for information about DATE headers
			self.imager.getpars = False	#Get camera parameters and print on the screen
			ret = self.imager.do ()
			
		except socket.error, e:
			print "Socket error: %s" % e
			print "ERROR"
			sys.exit (1)

		if ret:
			print "DONE"
		else:
			print "INTERRUPTED"

if __name__ == "__main__":

	base_directory = '/home/minerva/minerva_control'
	test_SI = SI_imager('SI_imager',base_directory)
	test_SI.test()
	
	
	
	
	
