import sys
import os
import socket
import logging
import json
import time
import threading
import datetime
from configobj import ConfigObj
sys.dont_write_bytecode = True
import mail

import pdu

from si.client import SIClient
from si.imager import Imager
#from si.commands import *
import dynapower
import ipdb
import utils

# spectrograph control class, control all spectrograph hardware
class spectrograph:

	def __init__(self,config, base ='', red=False, directory=None):

		self.lock = threading.Lock()
		self.si_lock = threading.Lock()
		self.config_file = config
		self.base_directory = base
		self.red = red
		self.load_config()
		self.logger = utils.setup_logger(self.base_directory,self.night(),self.logger_name)
		self.recovery=False
		self.skip_safe_close=False
		self.nfailed = 0.0

		self.create_class_objects()
		self.status_lock = threading.RLock()
		self.file_name = ''

		if directory == None:
                       if red: self.directory = 'directory_red.txt'
                       else: self.directory = 'directory.txt'
                else: self.directory=directory
		
		# configures camera
		self.initialize_si()


		# threading.Thread(target=self.write_status_thread).start()

	#load configuration file
	def load_config(self):
	
		try:
			config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.ip = config['SERVER_IP']
			self.port = int(config['SERVER_PORT'])
			self.camera_port = int(config['CAMERA_PORT'])
			self.logger_name = config['LOGNAME']
			self.exptypes = {'Template':1,
                                         'SlitFlat':1,
                                         'Arc':1,
                                         'FiberArc': 1,
                                         'FiberFlat':1,
                                         'Bias':0,
                                         'Dark':0,
                                        }
			self.si_settings = config['SI_SETTINGS']

			# reset the night at 10 am local
			today = datetime.datetime.utcnow()
                        if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                                today = today + datetime.timedelta(days=1)
                        #self.night = 'n' + today.strftime('%Y%m%d')
                        self.i2positions = config['I2POSITIONS']
                        for key in self.i2positions.keys():
                                self.i2positions[key] = float(self.i2positions[key])
                        self.thar_file = config['THARFILE']
                        self.flat_file = config['FLATFILE']
			self.i2settemp = float(config['I2SETTEMP'])
			self.i2temptol = float(config['I2TEMPTOL'])
			self.lastI2MotorLocation = 'UNKNOWN'

		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()


	def night(self):
		return 'n' + datetime.datetime.utcnow().strftime('%Y%m%d')

	def create_class_objects(self):
		if self.red:
			self.benchpdu = pdu.pdu('apc_mredbench.ini', self.base_directory)
			self.calpdu = pdu.pdu('apc_mred_cal.ini', self.base_directory)
		else:
			#TODO Should we have this here? It makes sense to give it the time
			#TODO to warm and settle.
			self.benchpdu = pdu.pdu('apc_bench.ini',self.base_directory)
			self.cell_heater_on()
			#self.connect_si_imager()
		
	#return a socket object connected to the camera server
	def connect_server(self):
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.settimeout(3)
			s.connect((self.ip, self.port))
			self.logger.info('successfully connected to spectrograph server')
			self.nfailed=0

		except:
			self.logger.error('failed to connect to spectrograph server')

			# this stops infinite recursion
			if not self.recovery:
				self.logger.error('beginning recovery')
				self.nfailed += 1
				if self.nfailed > 3:
					mail.send("The kiwispec server failed to connect","Dear Benevolent humans,\n\n"+
						  "The kiwspec server failed to connect 3 times in a row and I have no recovery procedure for this. Good luck!\n\n"+
						  "Love,\nMINERVA",level='serious', directory=self.directory)
					return s

				self.recovery=True
				self.skip_safe_close=True
				self.recover()
				self.logger.info('recovery attempt complete, trying to reconnect')
				result = self.connect_server()
				self.recovery=False
				self.skip_safe_close=False
				return result
				

			#ipdb.set_trace()
		return s
	#send commands to camera server running on telcom that has direct control over instrument
	def send(self,msg,timeout):
		self.logger.info("Beginning serial communications with the spectrograph server to send " + msg)
		
		if self.recovery: 
			self.logger.info("in recovery; overriding lock")
			try: self.lock.release()
			except:	self.logger.info("no lock to override")
		
		self.logger.info("acquiring lock")
		self.lock.acquire()

#		with self.lock:

		self.logger.info("trying to connect")
		s = self.connect_server()
		self.logger.info("connected")

		try:
			self.logger.info("setting timeout")
			s.settimeout(5)
			self.logger.info("sending msg: " + msg)
			s.sendall(msg)
			self.logger.info("done sending msg: " + msg)
		except:
			self.logger.error("connection lost")
			self.logger.info("releasing lock")
			try: self.lock.release()
			except: pass
			return 'fail'

		try:
			s.settimeout(timeout)
			data = s.recv(1024)
			s.close()
		except:
			self.logger.error("connection timed out")
			self.logger.exception("connection timed out")
			self.logger.info("releasing lock")
			try: self.lock.release()
			except: pass
			return 'fail'


		data = repr(data).strip("'")
		
		if len(data.split()) == 0:
			self.logger.error(msg.split()[0] + " command failed")
		elif data.split()[0] == 'success':
			self.logger.info(msg.split()[0] + " command completed")
		else:
			self.logger.error(msg.split()[0] + " command failed")

		self.logger.info("releasing lock")

		# JDE 2023-01-24
		# this is a hack! We need to find out why it's already released!
		try: self.lock.release()
		except: pass

		return data
		
	#get camera status and write into a json file with name == (self.logger_name + '.json')
	def write_status(self):
		res = self.send('get_status none',5).split(None,1)
		if res[0] == 'success':
			self.status_lock.acquire()
			status = open(self.base_directory+'/status/' + self.logger_name+ '.json','w')
			status.write(res[1])
			status.close()
			self.status_lock.release()
			self.logger.info('successfully wrote status')
			return True
		else:
			self.logger.error('failed to write status')
			return False
	#loop function used in a separate status thread
	def write_status_thread(self):
		while True:
			self.wite_status()
			time.sleep(10)
	#set path for which new images will be saved,if not set image will go into dump folder
	def set_data_path(self):
		
		if self.send('set_data_path',3) == 'success':
			self.logger.info('successfully set datapath') 
			return True
		else:
			self.logger.error('failed to set datapath')
			return False
	#get index of new image
	def get_index(self):
		res = self.send('get_index none',5).split()
		if res[0] == 'success': return int(res[1])
		else: return -1
	def get_filter_name(self):
		return self.send('get_filter_name none',5)
	def check_filters(self):
		filter_names = self.get_filter_name().split()
		if len(filter_names) != len(self.filters)+1:
			return False
		for i in range(len(self.filters)):
			if self.filters[i] != filter_names[i+1]:
				return False
		return True
	#ask remote telcom to connect to camera
	def connect_camera(self):
		if (self.send('connect_camera none',30)).split()[0] == 'success':
			if self.check_filters()==False:
				self.logger.error('mismatch filter')
				return False
			self.logger.info('successfully connected to camera')
			return True
		else:
			self.logger.error('failed to connected to camera')
			return False
			
	def set_binning(self):
		if self.send('set_binning ' + self.xbin + ' ' + self.ybin, 5) == 'success': return True
		else: return False
		
	def set_size(self):
		if self.send('set_size '+ self.x1 + ' ' + self.x2 + ' ' + self.y1 + ' ' + self.y2,5) == 'success': return True
		else: return False
			
	def settle_temp(self):
		threading.Thread(target = self.send,args=('settle_temp ' + self.setTemp,910)).start()

        def getexpflux(self, t0, tf=None, directory = '/Data/kiwilog/'):
                flux = 0.0
		night = t0.strftime('n%Y%m%d')
                with open(directory + night + '/expmeter.dat', 'r') as fh:
                        f = fh.read()
                        lines = f.split('\n')
                        for line in lines:
                                entries = line.split(',')
                                if len(entries[0]) == 26:
                                        date = datetime.datetime.strptime(entries[0], '%Y-%m-%d %H:%M:%S.%f')
					if tf != None:
						if date > t0 and date < tf: 
							flux += float(entries[1])
						elif date > tf:
							break
					else:
						if date > t0: flux += float(entries[1])
                return flux
                        
		
	# ##
	# SI IMAGER FUNCTIONS
	# ##

	def start_si_image(self):
		self.logger.info('Starting SI Imager SGL E on Kiwispec')
		response = self.send('start_si_image None',10)
		return response

	def kill_si_image(self):
		self.logger.info('Killing SI Imager SGL E on Kiwispec')
		response = self.send('kill_si_image None',10)
		return response

	# this will restart the SI imager. 
	# The cooler will turn off for ~15 seconds and take several minutes to cool back down
	def si_image_restart(self,sleeptime=1,timeout=30):
		self.logger.info('Restarting SI Image')
		self.kill_si_image()
		time.sleep(sleeptime)
		self.start_si_image()
		time.sleep(10)
		self.initialize_si()
		return True


	def si_recover(self):
		try: self.recover_attempts += 1
		except AttributeError: self.recover_attempts = 1

		if self.recover_attempts == 1:
			#S let's just try again? seems dangerous, could try a short exposure or something
			return True

		if self.recover_attempts == 2:
			#S now restart si image
			self.logger.info('si imager failed, attempting recovery '+str(self.recover_attempts))
			
			if self.si_image_restart():
				self.logger.info('restarted si image, and continuing')
			else:
				#S should we make a hold here, like a file that needs to be deleted?
				self.logger.exception('failed to restart si image')
				subject = 'Failed to restart SI Image'
				body = "Dear benevolent humans,\n\n"+\
				    "The SI Image software on Kiwispec failed to restart when attempting a recovery. "+\
				    "I need you to restart the software, and investigate why I went into recovery "+\
				    "in the first place.\n\n Love,\n MINERVA"
				mail.send(subject,body,level='serious', directory=self.directory)
				return False

	def expose_with_timeout(self,exptime=1.0, exptype=1, expmeter=None, timeout=None):
		if timeout == None:
			timeout = exptime + 120.0

		kwargs = {"exptime":exptime,"exptype":exptype,"expmeter":expmeter}
		thread = threading.Thread(target=self.expose,kwargs=kwargs)
		thread.name = 'kiwispec'
		thread.start()
		thread.join(timeout)
		if thread.isAlive():
			mail.send("The SI imager timed out","Dear Benevolent Humans,\n\n" + 
				  "The SI imager has timed out while exposing. This is usually "+
				  "due to an improperly aborted exposure, in which case someone "+
				  "needs to log into KIWISPEC-PC, click ok, and restart mainNew.py\n\n"
				  "Love,\n,MINERVA",level='serious', directory=self.directory)
			self.logger.error("SI imager timed out")
			sys.exit()
			return False
		return True


	#start exposure
	def expose_bad(self, exptime=1.0, exptype=1, expmeter=None):
		
#		imager = self.si_imager
#		"""
        	host = self.ip
                port = self.camera_port

		self.si_lock.acquire()
                client = SIClient (host, port)
                self.logger.info("Connected to SI client")

                imager = Imager(client)
                self.logger.info("Connected to SI imager")
#		"""
                self.si_imager = imager
                self.si_imager.nexp = 1		        # number of exposures
                self.si_imager.texp = exptime		# exposure time, float number
                self.si_imager.nome = "image"		# file name to be saved
		if exptype == 0: self.si_imager.dark = True
		else: self.si_imager.dark = False
                self.si_imager.frametransfer = False	# frame transfer?
                self.si_imager.getpars = False		# Get camera parameters and print on the screen

                # expose until exptime or expmeter >= flux
                t0 = datetime.datetime.utcnow()
                elapsedtime = 0.0
                flux = 0.0
                if expmeter <> None:
			#S reset the exposure meter
			self.reset_expmeter_total()
			#S begin the imaging thread
                        thread = threading.Thread(target=self.si_imager.do)
                        thread.start()
                        while elapsedtime < exptime:
				#S we are going to query the expmeter total every second
				#S probably could be finer resolution
                                time.sleep(1.0)
                                elapsedtime = (datetime.datetime.utcnow()-t0).total_seconds()
                                flux = self.get_expmeter_total()
                                self.logger.info("flux = " + str(flux))
                                if expmeter < flux:
					self.logger.info('got to flux of '+str(flux)+', greater than expmeter: '+str(expmeter))
					self.si_imager.interrupt()
                                        #imager.retrieve_image()
                                        break
			
                        #S this is on a level outside of the while for the elapsed time as the imager.do thread is 
			#S is still running. e.g., we still want to wait whether the elapsed time has gone through or
			#S the expmeter has triggered the interrupt.
			thread.join(60)
#			time.sleep(25)
			#S I don't know if this is true.. i think if we terminate it still might leave the imager.do thread alive..
			#TODO, or did you test this?
			if thread.isAlive():
				self.logger.error("SI imaging thread timed out. Releasing lock")
				# I think this is problematic. Do we need to kill it?
				self.si_imager.interrupt()
				self.si_lock.release()
				return False
                        
		else:
                        self.si_imager.do()
		#client.disconnect()
		self.si_lock.release()
                return self.save_image(self.file_name)

	#start exposure
	def expose(self, exptime=1.0, exptype=1, expmeter=None):
		
		self.si_lock.acquire()
                client = SIClient (self.ip, self.camera_port)
                self.logger.info("Connected to SI client")

                imager = Imager(client)
                self.logger.info("Connected to SI imager")

		# set up exposure
                imager.nexp = 1		        # number of exposures
                imager.texp = exptime		# exposure time, float number
                imager.nome = "image"		# file name to be saved
		if exptype == 0: imager.dark = True
		else: imager.dark = False
                imager.frametransfer = False	        # frame transfer?
                imager.getpars = False		# Get camera parameters and print on the screen

                self.logger.info("Exposing")
		imager.do()

                self.logger.info("Image done; disconnecting")
		client.disconnect()
		self.si_lock.release()
                return self.save_image(self.file_name)
 
	#block until image is ready, then save it to file_name
      	def set_file_name(self,file_name):
        	if self.send('set_file_name ' + file_name,30) == 'success': return True
		else: return False
	def save_image(self,file_name):
        	if self.send('save_image ' + file_name,30) == 'success': return True
		else: return False
	def image_name(self):
                return self.file_name
	#write fits header for self.file_name, header_info must be in json format
	def write_header(self, header_info):
		if self.file_name == '':
                        self.logger.error("self.file_name is undefined")
			return False
		i = 800
		length = len(header_info)
		while i < length:
			if self.send('write_header ' + header_info[i-800:i],3) == 'success':
				i+=800
			else:
                                self.logger.error("write_header command failed")
				return False

		if self.send('write_header_done ' + header_info[i-800:length],10) == 'success':
			return True
		else:
                        self.logger.error("write_header_done command failed")
			return False

	def send_to_computer(self, cmd):

                f = open(self.base_directory + '/credentials/authentication.txt','r')
                username = f.readline().strip()
                password = f.readline().strip()
                f.close()

                cmdstr = "cat </dev/null | winexe -U HOME/" + username + "%" + password + " //" + self.ip + " '" + cmd + "'"
                os.system(cmdstr)
#                self.logger.info('cmd=' + cmdstr + ', out=' + out + ', err=' + err)
                self.logger.info(cmdstr)

		'''
                if 'NT_STATUS_HOST_UNREACHABLE' in out:
                        self.logger.error('host not reachable')
                        mail.send(self.telid + ' is unreachable',
                                  "Dear Benevolent Humans,\n\n"+
                                  "I cannot reach " + self.telid + ". Can you please check the power and internet connection?\n\n" +
                                  "Love,\nMINERVA",level="serious")
                        return False
                elif 'NT_STATUS_LOGON_FAILURE' in out:
                        self.logger.error('Invalid credentials')
                        mail.send("Invalid credentials for " + self.telid,
                                  "Dear Benevolent Humans,\n\n"+
                                  "The credentials in " + self.base_directory +
                                  '/credentials/authentication.txt (username=' + username +
                                  ', password=' + password + ') appear to be outdated. Please fix it.\n\n' +
                                  'Love,\nMINERVA',level="serious")
                        return False
                elif 'ERROR: The process' in err:
                        self.logger.info('Task already dead')
                        return True
		'''
                return True
	def safe_close(self):
		if not self.skip_safe_close:
			if self.send('safe_close None',10) == 'success': return True
			else: return False
		return True

	def kill_remote_task(self,taskname):
		return self.send_to_computer("taskkill /IM " + taskname + " /f")
	def kill_server(self):
		self.safe_close()	
		return self.kill_remote_task('python.exe')
	def start_server(self):
                ret_val = self.send_to_computer('schtasks /Run /TN "spectrograph_server"')
                time.sleep(120)
		self.initialize_si()
                return ret_val

	def recover_server(self):
		self.logger.error("Spectrograph recovery called.")

		self.logger.info("Acquiring SI lock in recover_server (waiting up to 32 minutes for previous exposure to complete)")

		if self.si_lock.acquire(1920):
			self.logger.info("SI lock acquired; releasing")
		else:
			self.logger.error("We're probably gonna get some problematic popups here")
		self.si_lock.release()

		self.logger.info("Killing server!")
		self.kill_server()
		time.sleep(10)
		self.logger.error("Restarting server!")

		# this is always going to be true (?)
		return self.start_server()

        def recover(self):
		self.logger.info("Restarting SI Imager")
		self.si_recover()

		if self.recover_server(): return 'success'

		# never get here?	
		self.logger.info("I don't think I'll ever get here. Is this true?")
		self.logger.error("Called the recovery but we have no recovery procedure!")
		if self.red: specname = 'MRED'
		else: specname = 'Kiwispec'
		mail.send(specname + " spectrograph software crashed","Dear Benevolent humans,\n\n"+
			  "The " + specname + " spectrograph software has crashed and I have no recovery procedure for this. Good luck!\n\n"+
			  "Love,\nMINERVA",level='serious', directory=self.directory)
		return 'fail'

	def take_bias(self):
		self.take_dark(exptime=0)

	def take_dark(self,exptime=1):
		pass
        
	#TODO Can we change this to take a dict as an argument?
	def take_image(self,exptime=1,objname='test',expmeter=None):

                exptime = int(float(exptime)) #python can't do int(s) if s is a float in a string, this is work around
		#put together file name for the image
		ndx = self.get_index()
		if ndx == -1:
			self.logger.error("Error getting the filename index")
			self.file_name = ''
			return
			# already tried to recover. unrecoverable, infinite loop
			#self.recover()
			#return self.take_image(exptime=exptime,objname=objname,expmeter=expmeter)

		self.file_name = self.night() + "." + objname + "." + str(ndx).zfill(4) + ".fits"
		self.logger.info('Start taking image: ' + self.file_name)
		#chose exposure type
		if objname in self.exptypes.keys():
			exptype = self.exptypes[objname] 
		else: exptype = 1 # science exposure

                ## configure spectrograph
                # turn on I2 heater
                # move I2 stage
                # configure all lamps
                # open/close calibration shutter
                # Move calibration FW
                # begin exposure meter

                self.set_file_name(self.file_name)
		
		if self.red:
			if self.send('expose ' + str(exptime) + ' 1 None',10) <> 'success': return False
			time.sleep(exptime+3.0)

			filename = self.file_name

			if self.save_image(filename):
                                self.logger.info('Finish taking image: ' + filename)
                                return filename
                        else:
                                self.logger.error('Failed to save image: ' + filename)
		else:

			if self.expose_with_timeout(exptime=exptime, expmeter=expmeter):
				self.logger.info('Finished taking image: ' + self.file_name)
				self.nfailed = 0 # success; reset the failed counter
				return
			else: 
				self.logger.error('Failed to save image: ' + self.file_name)
				self.file_name = ''
				#self.recover()
				# self.si_recover()
				#return self.take_image(exptime=exptime,objname=objname,expmeter=expmeter) 

        ###
        # FIBER SWITCHER FUNCTIONS (MRED only)
        ###        
	def get_fiber_position(self):
		response = self.send('get_fiber_position None',10)
		if 'success' in response: return float(response.split()[1].split('\\')[0])
		return False
	def fiber_to_calibrate(self):
		response = self.send('fiber_to_calibrate None',10)
		if response == 'success': return True
		return False
	def fiber_to_science(self):
		response = self.send('fiber_to_science None',10)
		if response == 'success': return True
		return False


        ###
        # IODINE CELL HEATER FUNCTIONS
        ###
        
        def cell_heater_on(self):
                response = self.send('cell_heater_on None',10)
                return response
        def cell_heater_off(self):
                response = self.send('cell_heater_off None',10)
                return response
        #TODO I don't think the second split is necessary on all these 'returns'
        def cell_heater_temp(self):
                response = self.send('cell_heater_temp None',10)
		if response == 'fail': return False
                return float(response.split()[1].split('\\')[0])

        def cell_heater_set_temp(self, temp):
                response = self.send('cell_heater_set_temp ' + str(temp),10)
		print response

		if response == 'fail': return False
                return float(response.split()[1].split('\\')[0])

        def cell_heater_get_set_temp(self):
                response = self.send('cell_heater_get_set_temp None',10)
		if response == 'fail':return False
                return float(response.split()[1].split('\\')[0]) 


	def vent(self):

                ipdb.set_trace()

		timeout = 1200.0

		# close the vent valve
		self.logger.info("Closing the vent valve")
		self.benchpdu.ventvalve.off()
		
		# close the pump valve
		self.logger.info("Closing the pump valve")
		self.benchpdu.pumpvalve.off()

		# turn off the pump
		self.logger.info("Turning off the pump")
		self.benchpdu.pump.off()

                spec_pressure= self.get_spec_pressure()
                self.logger.info("Spectrograph pressure is " + str(spec_pressure) + " mbar")

		if spec_pressure < 500.0:
			mail.send("The spectrograph is pumped (" + str(spec_pressure) + " mbar and attempting to vent!","Manual login required to continue",level='Debug', directory=self.directory)
			self.logger.error("The spectrograph is pumped (" + str(spec_pressure) + " mbar and attempting to vent; manual login required to continue")
			ipdb.set_trace()
			time.sleep(60)

			# TODO: make hold file to restart thread
			
		# open the vent valve
                self.logger.info("Opening the vent valve")
		self.benchpdu.ventvalve.on()

		t0 = datetime.datetime.utcnow()
		elapsedtime = 0.0
                spec_pressure = self.get_spec_pressure()
		while spec_pressure < 500.0:
			elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds()
			self.logger.info('Waiting for spectrograph to vent (Pressure = ' + str(self.get_spec_pressure())\
						 + ' mbar; elapsed time = '+ str(elapsedtime) + ' seconds)')
                        spec_pressure = self.get_spec_pressure()

		# TODO: monitor pressure during venting and create smarter error condition                                                                                         
		if elapsedtime < timeout:
			time.sleep(5)
		else:
			self.logger.error("Error venting the spectrograph")
			return

		self.logger.info("Venting complete; spectrograph pressure is " + str(spec_pressure) + ' mbar')


	# pump down the spectrograph (during the day)
	def pump(self):

		timeout = 1200

		if self.get_spec_pressure() > 500:
			mail.send("The spectrograph is at atmosphere!","Manual login required to continue", level='serious', directory=self.directory)
			self.logger.error("The spectrograph is at atmosphere! Manual login required to continue")

			# TODO: make hold file to restart thread
			ipdb.set_trace()

		# close the vent valve
		self.logger.info("Closing the vent valve")
		self.benchpdu.ventvalve.off()

		# close the pump valve
		self.logger.info("Closing the pump valve")
		self.benchpdu.pumpvalve.off()

		# turn on the pump
		self.logger.info("Turning on the pump")
		self.benchpdu.pump.on()

		# wait until the pump gauge reads < 100 ubar
		t0 = datetime.datetime.utcnow()
		elapsedtime = 0.0
		pump_pressure = self.get_pump_pressure()
		while pump_pressure > 0.1:
			elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds()
			self.logger.info('Waiting for tube to pump down (Pressure = ' + str(pump_pressure) + 'mbar ; elapsed time = '+ str(elapsedtime) + ' seconds)')
			if elapsedtime < timeout:
				time.sleep(5)
			else:
				self.logger.error("Error pumping down the spectrograph")
				return
			pump_pressure = self.get_pump_pressure()


		# open the pump valve
		self.benchpdu.pumpvalve.on()
		self.logger.info("Pump gauge at " + str(pump_pressure) + " mbar; pumping down the spectrograph")

		# TODO: wait for pressure to go below some value??    
		t0 = datetime.datetime.utcnow()
		elapsedtime = 0.0
		spec_pressure = self.get_spec_pressure()
		while spec_pressure > 10:
			elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds()
			self.logger.info('Waiting for spectrograph to pump down (Pressure = ' + str(spec_pressure) + ' mbar; elapsed time = '+ str(elapsedtime) + ' seconds)')
			if elapsedtime < timeout:
				time.sleep(5)
			else:
				self.logger.error("Error pumping down the spectrograph")
				return
			spec_pressure = self.get_spec_pressure()

		self.logger.info("Spectrograph at " + str(spec_pressure) + " mbar; done")


	# close the valves, hold the pressure (during the night)
	def hold(self):
		# make sure the vent valve is closed
		self.logger.info("Closing vent valve")
		self.benchpdu.ventvalve.off()
		# close the pump valve
		self.logger.info("Closing pump valve")
		self.benchpdu.pumpvalve.off()
		# turn off the pump        
		self.logger.info("Turning off pump")
		self.benchpdu.pump.off()

			
	def get_spec_pressure(self):
                response = self.send('get_spec_pressure None',5)
                if response == 'fail':
                        return 'UNKNOWN'
		return float(response.split()[1])

	def get_pump_pressure(self):
                response = self.send('get_pump_pressure None',5)
                if response == 'fail':
                        return 'UNKNOWN'
		return float(response.split()[1])

        ###
        # THORLABS STAGE, For Iodine Cell
        ###

        #S Initialize the stage, needs to happen before anyhting else.
        def i2stage_connect(self):
                response = self.send('i2stage_connect None',30)
                return response
        
        #S Disconnect the i2stage. If not done correctly, python.exe crash will happen.
        #S There is a safety disconnect in the safe_close() of spectrograph_server.py. 
        def i2stage_disconnect(self):
                response = self.send('i2stage_disconnect None',10)
                return response
	
	#S Home the iodine stage. This will return a certain ValueError(?), which
	#S should be handled on the spectrograph server side. 
	def i2stage_home(self, timeout=60):
		response = 'fail'
		t0 = datetime.datetime.now()
		elapsedTime = (datetime.datetime.now() - t0).total_seconds()
		while response=='fail' and elapsedTime < timeout:
			elapsedTime = (datetime.datetime.now() - t0).total_seconds()
			response = self.send('i2stage_home None',10)
			if response=='fail': time.sleep(1)

		if response=='fail': 
			self.nfailed += 1
			self.recover()
			if self.nfailed > 3:
				mail.send("The iodine stage failed","Dear Benevolent humans,\n\n"+
					  "The iodine stage failed to home 3 times in a row and I have no recovery procedure for this. Good luck!\n\n"+
					  "Love,\nMINERVA",level='serious', directory=self.directory)
				return 'fail'

			return i2stage_home()

		self.nfailed = 0.0
		return response

        #S Query the position of the i2stage. 
        #S response is 'success '+str(position)
        def i2stage_get_pos(self):
                response = self.send('i2stage_get_pos None',10)
		if response == 'fail': return 'fail -999'
		return [float(response.split()[1].split('\\')[0]),response.split()[2]]

        #S Send a command to move the i2stage to one of the set positions.
        #S The positions are defined in spectrograph.ini AND spectrograph_server.ini,
        #S but I'm fairly certain they don't need to be in spectrograph.ini. Left
        #S Them just in case.
        def i2stage_move(self,locationstr):
                #S some hackery for writing info to headers in control.py
                #TODO Can and should be gone about in a better way
                self.lastI2MotorLocation = locationstr
                response = self.send('i2stage_move '+locationstr,10)

		# potential infinite loop
		if response == 'fail': 
			self.recover()
			return self.i2stage_move(locationstr)
                return response

	# move the stage to an arbitrary position
        def i2stage_movef(self,position):
                self.lastI2MotorLocation = 'UNKNOWN'
                response = self.send('i2stage_movef '+str(position),10)
                return response

        ###
        # THAR AND FLAT LAMPS
        ###

        #S Functions for toggling the ThAr lamp
        def thar_turn_on(self):
                response = self.send('thar_turn_on None',10)
                return response

        def thar_turn_off(self):
                response = self.send('thar_turn_off None',10)
                return response

        #S Functions for toggling the flat lamp
        def flat_turn_on(self):
                response = self.send('flat_turn_on None',10)
                return response

        def flat_turn_off(self):
                response = self.send('flat_turn_off None',10)
                return response

        def backlight_on(self):
                response = self.send('backlight_on None',10)
		if response == 'fail':
			self.backlight_power_cycle()
			response = self.send('backlight_on None',10)
		return response

        def backlight_off(self):
                response = self.send('backlight_off None',10)
		if response == 'fail':
			self.backlight_power_cycle()
			response = self.send('backlight_off None',10)
		return response

	def backlight_power_cycle(self):
		response = self.send('backlight_power_cycle',60)
		return response

        def led_turn_on(self):
                response = self.send('led_turn_on None',10)
                return response
	
        def led_turn_off(self):
                response = self.send('led_turn_off None',10)
                return response

	def get_expmeter_total(self):
		response = self.send('get_expmeter_total None',10)
		return float(response.split()[1])

	def reset_expmeter_total(self):
		response = self.send('reset_expmeter_total None',10)
		return response

        #S This is used to check how long the lamp has been turned on for
        #S from the LAST time it was turned on, not total time on. Used
        #S for equipment checks in control.py, so needed to send to
        #S the server.
        def time_tracker_check(self,filename):
                response = self.send("time_tracker_check "+filename,10)
                return float(response.split()[1].split('\\')[0])
        

	def stop_log_expmeter(self):
		response = self.send('stop_log_expmeter None',30)
	def start_log_expmeter(self):
		response = self.send('start_log_expmeter None',10)

	"""
        #S Dynapowers are now objects for the spectrograph server to control,
        #S but we still need to communicate statuses from server to write
        #S headers in control.py. Made this weird attribute for spectrograph
        #S objects, dynapower status. We only have two dynapowers anyway,
        #S so I'm thinking this will be fine.
        #S Another thought was to give spectrograph object its own dynapower
        #S classes, but this could create confusion and we should try and keep
        #S them localizex.
        def update_dynapower1(self):
                #S the current response from the server is a 'success '+json.dumps(status_dictionary)
                #S so we need to do some tricky parsing. 
                temp_response = self.send('update_dynapower1 None',10)
                #S Empty string where we'll be putting dictionary entries.
                status_str = ''
                #S This splits the response string at spaces, then concatenates all but the first
                #S split, which was 'success'. Look at how json.dumps writes strings to see why this
                #S works
                for p in temp_response.split(' ')[1:]:
                        status_str = status_str + p + ' '
                #S assign that attribute dictionary to the json.loads(status_str)        
                self.dynapower1_status = json.loads(status_str)
        def update_dynapower2(self):
                temp_response = self.send('update_dynapower2 None',10)
                status_str = ''
                for p in temp_response.split(' ')[1:]:
                        status_str = status_str + p + ' '
                self.dynapower2_status = json.loads(status_str)
	"""

	def initialize_si(self):
		self.si_lock.acquire()
		client = SIClient(self.ip, self.camera_port)
		imager = Imager(client)
		imager.setReadoutMode(3)
		imager.setCCDFormatParameters(50,2090,1,0,2052,1)
		imager.coolerON() # doesn't work (just not reflected in the GUI?)
		client.disconnect()
		self.si_lock.release()

if __name__ == '__main__':
	
	base_directory = '/home/minerva/minerva-control'
        if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	spec = spectrograph('spectrograph.ini',base_directory)
#        spec.pump()

	client = SIClient(spec.ip, spec.camera_port)
	imager = Imager(client)

	ipdb.set_trace()
	while True:
		print 'spectrograph_control test program'
		print ' a. take_image'
		print ' b. expose'
		print ' c. set_data_path'
		print ' d. set_binning'
		print ' e. set_size'
		print ' f. settle_temp'
		print ' g. vacuum pressure'
		print ' h. atmospheric pressure'
		print ' i. dummy'
		print '----------------------------'
		choice = raw_input('choice:')

		if choice == 'a':
			pass
		elif choice == 'b':
			spec.expose()
		elif choice == 'c':
			spec.set_data_path()
		elif choice == 'd':
			spec.set_binning()
		elif choice == 'e':
			spec.set_size()
		elif choice == 'f':
			spec.settle_temp()
		elif choice == 'g':
			print spec.get_vacuum_pressure()
		elif choice == 'h':
			print spec.get_atmospheric_pressure()
		else:
			print 'invalid choice'
			
			
	
