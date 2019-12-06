import sys
import os
import socket
import errno
import logging
import time
import threading
import pdu
import telcom_client
import mail
import datetime
from configobj import ConfigObj
import ipdb
import subprocess
import cdk700
sys.dont_write_bytecode = True
import numpy as np
import utils

class fau:

	def __init__(self,config, base =''):

		self.config_file = config
		self.telnum = config[-5]
		self.base_directory = base
		self.load_config()
		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
		self.initialize()
#		self.telcom = telcom_client.telcom_client(self.telcom_client_config,base)
#		self.status_lock = threading.RLock()
		# threading.Thread(target=self.write_status_thread).start()

	def initialize(self):
		return
		if not self.connect_camera(): self.recover()
		self.set_binning()
		self.set_size()

	def filterdata(self, vals, N=5):
		if vals.size < N:
        #S Returns the last element, but how is this equivalent to the else? Too few elements?
        #S No catch if vals.size > N? Need to figure what this is trying to do.
			return vals[-1]
		else:
			kernel=np.ones(N)/N
			return np.convolve(vals, kernel, 'valid')[-1]

	#S Returns a normalized unit vector in the direction of deltax, deltay.
	def dist(self, deltax, deltay):
		return np.linalg.norm((deltax, deltay))

        #S Creates a 2D rotation matrix given an angle theta.
	def rotmatrix(self,theta):
		thetarad = np.pi/180.0*theta
		return np.array([[np.cos(thetarad), -np.sin(thetarad)],
				 [np.sin(thetarad), np.cos(thetarad)]])

	def firstmove(self):
		pass

	def load_config(self):
	
		try:
			# common to spectrograph detector and imaging camera
                        config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.guiding = False

			self.badpix = self.base_directory + '/config/' + config['Setup']['BADPIX']

			self.KPx = float(config['Loop_params']['KPx'])
			self.KIx = float(config['Loop_params']['KIx'])
			self.KDx = float(config['Loop_params']['KDx'])
			self.KPy = float(config['Loop_params']['KPy'])
			self.KIy = float(config['Loop_params']['KIy'])
			self.KDy = float(config['Loop_params']['KDy'])
			self.Dband = float(config['Loop_params']['Deadband'])
			self.Imax = float(config['Loop_params']['Imax'])
			self.Corr_max = float(config['Loop_params']['Corr_max'])
			
			self.fKPx = float(config['Fast_Loop_params']['KPx'])
			self.fKIx = float(config['Fast_Loop_params']['KIx'])
			self.fKDx = float(config['Fast_Loop_params']['KDx'])
			self.fKPy = float(config['Fast_Loop_params']['KPy'])
			self.fKIy = float(config['Fast_Loop_params']['KIy'])
			self.fKDy = float(config['Fast_Loop_params']['KDy'])
			self.fDband = float(config['Fast_Loop_params']['Deadband'])
			self.fImax = float(config['Fast_Loop_params']['Imax'])
			self.fCorr_max = float(config['Fast_Loop_params']['Corr_max'])
			
			self.bp = float(config['Bp_arcsec']['bp'])
			
			self.rotangle= float(config['Tel_params']['rotangle'])
			self.platescale= float(config['Tel_params']['platescale'])
			
			self.smoothing = int(config['Scale_params']['smoothing'])

			self.ip = config['Setup']['SERVER_IP']
			self.port = int(config['Setup']['SERVER_PORT'])

			self.logger_name = config['Setup']['LOGNAME']

			self.xbin = int(config['Setup']['XBIN'])
			self.ybin = int(config['Setup']['YBIN'])
			self.xfiber = float(config['Setup']['XFIBER'])
			self.yfiber = float(config['Setup']['YFIBER'])
			self.xcenter = float(config['Setup']['XCENTER'])
			self.ycenter = float(config['Setup']['YCENTER'])
			self.acquisition_tolerance = float(config['Setup']['ACQUISITION_TOLERANCE'])
			self.x1 = int(config['Setup']['X1'])
			self.x2 = int(config['Setup']['X2'])
			self.y1 = int(config['Setup']['Y1'])
			self.y2 = int(config['Setup']['Y2'])

			try: self.focusOffset = float(config['Setup']['FOCUSOFFSET'])
			except: self.focusOffset = 0.0

			self.biaslevel = float(config['Setup']['BIASLEVEL'])
			self.saturation = float(config['Setup']['SATURATION'])
			self.datapath = ''
			self.gitpath = ''
			self.file_name = 'test'
			self.night = 'test'
			self.nfailed = 0
			self.nserver_failed = 0
			self.acquired = False
			self.failed = False

		except:
			print('ERROR accessing config file: ' + self.config_file)
			sys.exit()

                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')
		
#	#get camera status and write into a json file with name == (self.logger_name + 'json')#
#	def write_status(self):
#		res = self.send('get_status none',5).split(None,1)
#		if res[0] == 'success':
#			self.status_lock.acquire()
#			status = open(self.base_directory+'/status/' + self.logger_name + '.json','w')
#			status.write(res[1])
#			status.close()
#			self.status_lock.release()
#			return True
#		else:
#			return False
#	#status thread
#	def write_status_thread(self):
#		
#		for i in threading.enumerate():
#				if i.name == "MainThread":
#					main_thread = i
#					break
#		n = 15
#		while True:
#			if main_thread.is_alive() == False:
#				break
#			n+= 1
#			if n > 14:
#				self.write_status()
#				n = 0
#			time.sleep(1)
#			
#	#set path for which new images will be saved,if not set image will go into dump folder
#	def set_dataPath(self):
#		
#		if self.send('set_data_path none',3) == 'success':
#			return True
#		else:
#			return False
#	#get index of new image
#	def get_index(self):
#		res = self.send('get_index none',5).split()
#		if res[0] == 'success': return int(res[1])
#		else: return -1
	def write_header(self, header_info):
		if self.file_name == '':
			self.logger.error('Empty file name')
			return False
		i = 800
		length = len(header_info)
		while i < length:
			if self.send('write_header ' + header_info[i-800:i],3) == 'success':
				i+=800
			else:
				self.logger.error('Error sending header string::: ' +header_info[i-800:i])
				return False

		if self.send('write_header_done ' + header_info[i-800:length],10) == 'success':
			return True
		else:
			self.logger.error('Failed to finish writing header')			
			return False
		
#test program, edit camera name to test desired camera
if __name__ == '__main__':

	if socket.gethostname() == 'Main':
        	base_directory = '/home/minerva/minerva-control'
        	config_file = 'fau_t1.ini'
        else:
                base_directory = 'C:/minerva-control/'
                config_file = 'fau_t' + socket.gethostname()[1] + '.ini'
                
	test_imager = imager(config_file,base_directory)
	ipdb.set_trace()
	while True:
		print 'camera_control test program'
		print ' a. take_image'
		print ' b. expose'
		print ' c. set_data_path'
		print ' d. set_binning'
		print ' e. set_size'
		print ' f. settle_temp'
		print ' g. compress_data'
		print ' h. getMean'
		print ' i. getMode'
		print ' j. isSuperSaturated'
		print ' k. remove'
		print ' l. write_header'
		print ' m. connect_camera'
		print ' n. disconnect_camera'
		print ' o. powercycle'
		print ' q. recover'
		print '----------------------------'
		choice = raw_input('choice:')

		if choice == 'a':
			test_imager.take_image(1.0,'zp','test')
		elif choice == 'b':
			test_imager.expose()
		elif choice == 'c':
			test_imager.set_data_path()
		elif choice == 'd':
			test_imager.set_binning()
		elif choice == 'e':
			test_imager.set_size()
		elif choice == 'f':
			test_imager.settle_temp()
		elif choice == 'g':
			test_imager.compress_data()
		elif choice == 'h':
			test_imager.getMean()
		elif choice == 'i':
			test_imager.getMode()
		elif choice == 'j':
			test_imager.isSuperSaturated()
		elif choice == 'k':
			test_imager.remove()
		elif choice == 'l':
			test_imager.write_header('{"status":["normal","abnormal"]}')
		elif choice == 'm':
			test_imager.connect_camera()
		elif choice == 'n':
			test_imager.disconnect_camera()
		elif choice == 'o':
			test_imager.powercycle()
		elif choice == 'q':
			test_imager.recover()
		else:
			print 'invalid choice'
			
			
	
