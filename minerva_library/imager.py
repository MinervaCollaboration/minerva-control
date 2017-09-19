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
import fau
sys.dont_write_bytecode = True
import utils

class imager:

	def __init__(self,config, base =''):

		self.lock = threading.Lock()
		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
		self.pdu = pdu.pdu(self.pdu_config,base)
		self.initialize()
		self.telcom = telcom_client.telcom_client(self.telcom_client_config,base)
		self.status_lock = threading.RLock()
		self.mailsent = False
		# threading.Thread(target=self.write_status_thread).start()

	def initialize(self):
		if not self.connect_camera(): self.recover()
		self.set_binning()
		self.set_size()
		self.set_temperature()
		
	def load_config(self):
		try:
                        # common to spectrograph detector and imaging camera
                        config = ConfigObj(self.base_directory + '/config/' + self.config_file)

			self.ip = config['Setup']['SERVER_IP']
			self.port = int(config['Setup']['SERVER_PORT'])
			self.logger_name = config['Setup']['LOGNAME']
			self.setTemp = float(config['Setup']['SETTEMP'])
			self.maxcool = float(config['Setup']['MAXCOOLING'])
			self.maxdiff = float(config['Setup']['MAXTEMPERROR'])
			self.xbin = int(config['Setup']['XBIN'])
			self.ybin = int(config['Setup']['YBIN'])
			self.xcenter = config['Setup']['XCENTER']
			self.ycenter = config['Setup']['YCENTER']
			self.x1 = config['Setup']['X1']
			self.x2 = config['Setup']['X2']
			self.y1 = config['Setup']['Y1']
			self.y2 = config['Setup']['Y2']
			self.biaslevel = float(config['Setup']['BIASLEVEL'])
			self.saturation = float(config['Setup']['SATURATION'])
			self.flattargetcounts = float(config['Setup']['FLATTARGETCOUNTS'])
			self.flatminexptime = float(config['Setup']['FLATMINEXPTIME'])
			self.flatmaxexptime = float(config['Setup']['FLATMAXEXPTIME'])
			self.flatminsunalt = float(config['Setup']['FLATMINSUNALT'])
			self.flatmaxsunalt = float(config['Setup']['FLATMAXSUNALT'])
			self.datapath = ''
			self.gitpath = ''
			self.file_name = 'test'
			self.night = 'test'
			self.nfailed = 0
			self.nserver_failed = 0
			self.pdu_config = config['Setup']['PDU']			
			
			# imaging camera 
			self.telcom_client_config = config['Setup']['TELCOM']
			self.platescale = float(config['Setup']['PLATESCALE'])
			self.filters = config['FILTERS']
			self.pointingModel = config['Setup']['POINTINGMODEL']
			self.telescope_name = config['Setup']['TELESCOPE']
			self.telid = config['Setup']['TELESCOPE']
			self.telnum = self.telescope_name[1]
			self.exptypes = {'Dark' : 0,'Bias' : 0,'SkyFlat' : 1,}
			self.fau_config = config['Setup']['FAU_CONFIG']

			# fau
			self.fau = fau.fau(self.fau_config,self.base_directory)

 		except:
			print('ERROR accessing config file: ' + self.config_file)
			sys.exit()

                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')
		
	#return a socket object connected to the camera server
	def connect_server(self):
		telescope_name = 'T' + self.telnum + ': '

		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.settimeout(3)
			s.connect((self.ip, self.port))
		except socket.error as e:
			if e.errno == errno.ECONNREFUSED:
				self.logger.error(telescope_name + 'connection failed (socket.error)')
			else: self.logger.exception(telescope_name + 'connection failed')
			return False
		except:
			self.logger.exception(telescope_name + 'connection failed')
			return False

		self.nserver_failed = 0
		return s
	#send commands to camera server
	def send(self,msg,timeout):

		self.logger.debug("Beginning serial communications with the imager server")
		if True:

			telescope_name = 'T' + self.telnum + ': '
			try:
				s = self.connect_server()
			except:
				self.logger.error(telescope_name + "connection lost")
				if self.recover_server(): return self.send(msg,timeout) 
				return 'fail'
			try: 
				s.settimeout(3)
			except:
				self.logger.error(telescope_name + "failed to set timeout")
				if self.recover_server(): return self.send(msg,timeout) 
				return 'fail'
			
			try:
				s.sendall(msg)
			except:
				self.logger.error(telescope_name + "failed to send message (" + msg + ")")
				if self.recover_server(): return self.send(msg,timeout) 
				return 'fail'

			try:
				s.settimeout(timeout)
				data = s.recv(1024)
			except:
				self.logger.error(telescope_name + "connection timed out")
				if self.recover_server(): return self.send(msg,timeout)
				return 'fail'

			try:
				command = msg.split()[0]
				data = repr(data).strip("'")
				data_ret = data.split()[0]
			except:
				self.logger.error(telescope_name + "error processing server response")
				if self.recover_server(): return self.send(msg,timeout)
				return 'fail'

			if data_ret == 'fail': 
				self.logger.error(telescope_name + "command failed("+command+')')
				return 'fail'

			return data
		
	def cool(self):
		telescope_name = 'T' + self.telnum + ': '

		settleTime = 1200
                oscillationTime = 120.0
		
                self.logger.info(telescope_name + 'Turning cooler on')
		self.set_temperature()

                start = datetime.datetime.utcnow()
                currentTemp = self.get_temperature()
		if currentTemp == 'fail':
			self.recover()
			currentTemp = self.get_temperature()
                if currentTemp == -999.0:
                        self.logger.warning(telescope_name + 'The camera failed to connect properly; beginning recovery')
                        if self.recover(): return self.cool()
			return False

                elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
                lastTimeNotAtTemp = datetime.datetime.utcnow() - datetime.timedelta(seconds=oscillationTime)
                elapsedTimeAtTemp = oscillationTime

		# Wait for temperature to settle (timeout of 15 minutes)
#		self.logger.error("***COOLING DISASBLED!!!***")#
#		return True

                while elapsedTime < settleTime and ((abs(self.setTemp - currentTemp) > self.maxdiff) or elapsedTimeAtTemp < oscillationTime):
                        self.logger.info(telescope_name + 'Current temperature (' + str(currentTemp) +
                                         ') not at setpoint (' + str(self.setTemp) +
                                         '); waiting for CCD Temperature to stabilize (Elapsed time: '
                                         + str(elapsedTime) + ' seconds)')

			# has to maintain temp within range for 1 minute
			if (abs(self.setTemp - currentTemp) > self.maxdiff):
                                lastTimeNotAtTemp = datetime.datetime.utcnow()
			elapsedTimeAtTemp = (datetime.datetime.utcnow() - lastTimeNotAtTemp).total_seconds()

                        time.sleep(10)
			#S update the temperature
                        currentTemp = self.get_temperature()
			#S check to see if we are actually getting temperatures. 
			if currentTemp == 'fail':
				self.recover()
				self.currentTemp = self.get_temperature()

                        elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
                # Failed to reach setpoint 
                if (abs(self.setTemp - currentTemp)) > self.maxdiff:
                        self.logger.error(telescope_name + 'The camera was unable to reach its setpoint (' +
                                          str(self.setTemp) + ') in the elapsed time (' +
                                          str(elapsedTime) + ' seconds)')
                        return False

                return True

	# ask server to connect to camera
	def connect_camera(self):
		telescope_name = 'T' + self.telnum + ': '

		if (self.send('connect_camera none',30)).split()[0] == 'success':
			if self.check_filters()==False:
				self.logger.error(telescope_name + 'mismatch filter')
				return False
			self.logger.info(telescope_name + 'successfully connected to camera')
			return True
		else:
			self.logger.error(telescope_name + 'failed to connected to camera')
			return False

	def disconnect_camera(self):
		
		telescope_name = 'T' + self.telnum + ': '
		if self.send('disconnect_camera none',15) == 'success':
			self.logger.info(telescope_name + 'successfully disconnected camera')
			return True
		else:
			self.logger.error(telescope_name + 'failed to disconnect camera')
			return False
			
	#get camera status and write into a json file with name == (self.logger_name + 'json')
	def write_status(self):
		res = self.send('get_status none',15).split(None,1)
		if res[0] == 'success':
			self.status_lock.acquire()
			status = open(self.base_directory+'/status/' + self.logger_name + '.json','w')
			status.write(res[1])
			status.close()
			self.status_lock.release()
			return True
		else:
			return False
	#status thread
	def write_status_thread(self):
		
		for i in threading.enumerate():
				if i.name == "MainThread":
					main_thread = i
					break
		n = 15
		while True:
			if main_thread.is_alive() == False:
				break
			n+= 1
			if n > 14:
				self.write_status()
				n = 0
			time.sleep(1)
			
	#set path for which new images will be saved,if not set image will go into dump folder
	def set_dataPath(self):
		
		if self.send('set_data_path none',3) == 'success':
			return True
		else:
			return False
	#get index of new image
	def get_index(self):
		res = self.send('get_index none',5).split()
		if res[0] == 'success': return int(res[1])
		else: return -1
	def get_filter_name(self):
		return self.send('get_filter_name ' + str(len(self.filters)),5)
	
	def getMean(self):
		res = self.send('getMean none',15).split()
		if res[0] == 'success':
			return float(res[1])
		else:
			return -9999
	
	def getMode(self):
		res = self.send('getMode none',15).split()
		if res[0] == 'success':
			return float(res[1])
		else:
			return -1
	
	def isSuperSaturated(self):
		res = self.send('isSuperSaturated none', 15).split()
		if res[0] == 'success':
			if res[1] == 'true':
				return True
		return False

	def remove(self):
		res = self.send('remove none',5).split()
		if res[0] == 'success':
			return True
		else:
			return False
	
	def check_filters(self):
		filter_names = self.get_filter_name().split()
			
		if len(filter_names) != len(self.filters)+1:
			return False
		for i in range(len(self.filters)):
			if filter_names[i+1] not in self.filters.keys():
				return False
		return True
			
	def set_binning(self):
		if self.send('set_binning ' + str(self.xbin) + ' ' + str(self.ybin), 5) == 'success': return True
		else: return False
		
	def set_size(self):
		if self.send('set_size '+ self.x1 + ' ' + self.x2 + ' ' + self.y1 + ' ' + self.y2,5) == 'success': return True
		else: return False
			
	def set_temperature(self):
		if self.send('set_temperature '+ str(self.setTemp),5) == 'success': return True
		else: return False

	def get_temperature(self):
		telescope_name = 'T' + self.telnum + ': '

		result = self.send('get_temperature none',5)
		try:
			if 'success' in result:
				temp = result.split()
				if len(temp) != 2:
					self.logger.error(telescope_name + 'parameter error')
					return 'fail'
				return float(temp[1])
			else: 
				self.logger.error(telescope_name + ' failed at getting temperature')
				return 'fail'
		except: 
			self.logger.exception(telescope_name + 'Unknown error getting temperature')
			return 'fail'

	def moveAO(self,north,east):
		cmd = 'moveAO ' + str(north) + ',' + str(east)
		if (self.send(cmd,30)).split()[0] == 'success': return True
		return False

	def homeAO(self):
		cmd = 'homeAO'
		if (self.send(cmd,30)).split()[0] == 'success': return True
		return False

	#start exposure
	def expose(self, exptime=1, exptype=0, filterInd=None,guider=False):
		self.logger.info('Starting exposure')
		cmd = 'expose'
		if guider: cmd += 'Guider'
		cmd += " " + str(exptime)

		if not guider:
			cmd += ' ' + str(exptype) + ' ' + str(filterInd)

		self.logger.info("sending command:" + cmd)
		if (self.send(cmd,30)).split()[0] == 'success': return True
		else: return False

	#block until image is ready, then save it to file_name
	def save_image(self,file_name,fau=False):
		cmd = 'save_image ' + file_name
		if fau: cmd += " fau"
		if self.send(cmd,30) == 'success': return True
		else: return False

	#write fits header for self.file_name, header_info must be in json format
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

	# returns file name of the image saved, return 'error' if error occurs
	def take_image(self,exptime=1,filterInd=None,objname = 'test' , fau=False):		
		telescope_name = 'T' + self.telnum + ': '
#		exptime = int(float(exptime)) #python can't do int(s) if s is a float in a string, this is work around
		#put together file name for the image
		ndx = self.get_index()
		if ndx == -1:
			self.logger.error(telescope_name + "Error getting the filename index")
			if self.recover(): return self.take_image(exptime=exptime, filterInd=filterInd,objname=objname, fau=fau)
			self.file_name = ''
			return 'error'

		if fau:	
			self.file_name = self.night + "." + self.telescope_name + ".FAU." + objname + "." + str(ndx).zfill(4) + ".fits"
			exptype = 1
		else: 
			if filterInd == None: self.file_name = self.night + "." + self.telescope_name + "." + objname + "." + str(ndx).zfill(4) + ".fits"
			else: self.file_name = self.night + "." + self.telescope_name + "." + objname + "." + filterInd + "." + str(ndx).zfill(4) + ".fits"
			# chose exposure type
			if objname in self.exptypes.keys():
				exptype = self.exptypes[objname] 
			else: exptype = 1 # science exposure

			# chose appropriate filter
			if filterInd != None and filterInd not in self.filters:
				self.logger.error(telescope_name + "Requested filter (" + filterInd + ") not present")
				self.file_name = ''
				return 'error'

		self.logger.info(telescope_name + 'start taking image: ' + self.file_name)
		if filterInd != None: filt = filt = self.filters[filterInd]
		else: filt = None
		
		if self.expose(exptime,exptype,filt,guider=fau):
			self.write_status()
			time.sleep(exptime)
			if self.save_image(self.file_name, fau=fau):
				self.logger.info(telescope_name + 'finish taking image: ' + self.file_name)
				self.nfailed = 0 
				return self.file_name
			else: 
				self.logger.error(telescope_name + 'failed to save image: ' + self.file_name)
				self.file_name = ''
				if self.recover(): return self.take_image(exptime=exptime, filterInd=filterInd,objname=objname, fau=fau)

		self.logger.error(telescope_name + 'taking image failed, image not saved: ' + self.file_name)
		self.file_name = ''
		return 'error'		

	def compress_data(self,night=None):
		#S I think we've given this too short of a time to reasonably compress
		#S the amount of data? On a few instances the thread died from connection being lost
		#S due to timeout.
		#TODO Increase tiimeout
		if night==None:
			night = self.night
		if self.send('compress_data '+night,30) == 'success': return True
		else: return False

	def powercycle(self,downtime=30):
                self.pdu.inst.off()
                time.sleep(downtime)
                self.pdu.inst.on()
		time.sleep(30)

	# this requires winexe on linux and a registry key on each Windows (7?) machine (apply keys.reg in dependencies folder):
	def recover_server(self):
                telescope_name = 'T' + self.telnum + ': '

		self.nserver_failed += 1

		# if it's failed more than 3 times, something is seriously wrong -- give up
		if self.nserver_failed > 3:
			if not self.mailsent: mail.send(telescope_name + 'Server failed','',level='serious')
			self.mailsent = True
			sys.exit()
		
		self.logger.warning(telescope_name + 'Server failed, beginning recovery') 

		# if these don't work, we're in trouble		
		if not self.kill_server(): return False
		if not self.kill_maxim(): return False

		# restart the server
		time.sleep(10)
                self.logger.warning(telescope_name + 'Restarting server') 		
                if not self.start_server(): 
			self.logger.error(telescope_name + "failed to start server")
			return False
		return True

		# if it's failed more than once, try power cycling the camera before restarting
		if self.nserver_failed > 1:
			self.logger.warning(telescope_name + 'Server failed more than once; power cycling the camera')
			self.powercycle()
			time.sleep(20)

		# restart the server
		time.sleep(10)
                self.logger.warning(telescope_name + 'Restarting server') 		
                if not self.start_server(): 
			self.logger.error(telescope_name + "failed to start server")
			return False

		return True

        def kill_remote_task(self,taskname):
                return self.send_to_computer("taskkill /IM " + taskname + " /f")
        def kill_server(self):
                return self.kill_remote_task('python.exe')
        def quit_maxim(self):
		return (self.send('quit_maxim none',30)).split()[0] == 'success'		
        def kill_maxim(self):
                return self.kill_remote_task('MaxIm_DL.exe')
        def kill_PWI(self):
		# disconnect telescope gracefully first (PWI gets angry otherwise)!
		config_file = 'telescope_' + self.telnum + '.ini'
		telescope = cdk700.CDK700(config_file,self.base_directory)
		try: telescope.shutdown()
		except: pass
		
                return self.kill_remote_task('PWI.exe')
        def start_server(self):
                ret_val = self.send_to_computer('schtasks /Run /TN "telcom server"')
		time.sleep(30)
		return ret_val

        def send_to_computer(self, cmd):
		f = open(self.base_directory + '/credentials/authentication.txt','r')
		username = f.readline().strip()
                password = f.readline().strip()
		f.close()

#                process = subprocess.Popen(["winexe","-U","HOME/" + username + "%" + password,"//" + self.ip, cmd],stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#		out,err = process.communicate()
#		FNULL = open(os.devnull, 'w')
#                process = subprocess.Popen(["winexe","-U","HOME/" + username + "%" + password,"//" + self.ip, cmd],stdout=FNULL, stderr=FNULL)
#		out,err = process.communicate()
		out = ''
		err = ''
		cmdstr = "cat </dev/null | winexe -U HOME/" + username + "%" + password + " //" + self.ip + " '" + cmd + "'"
		os.system(cmdstr)
		self.logger.info('T' + self.telnum + ': cmd=' + cmd + ', out=' + out + ', err=' + err)
		self.logger.info(cmdstr)

                if 'NT_STATUS_HOST_UNREACHABLE' in out:
                        self.logger.error('T' + self.telnum + ': the host is not reachable')
                        mail.send("T" + self.telnum + 'is unreachable',
                                  "Dear Benevolent Humans,\n\n"+
                                  "I cannot reach T" + self.telnum + ". Can you please check the power and internet connection?\n\n" +
                                  "Love,\nMINERVA",level="serious")			
                        return False
                elif 'NT_STATUS_LOGON_FAILURE' in out:
                        self.logger.error('T' + self.telnum + ': invalid credentials')
                        mail.send("Invalid credentials for T" + self.telnum,
                                  "Dear Benevolent Humans,\n\n"+
                                  "The credentials in " + self.base_directory +
                                  '/credentials/authentication.txt (username=' + username +
                                  ', password=' + password + ') appear to be outdated. Please fix it.\n\n' +
                                  'Love,\nMINERVA',level="serious")
                        return False
                elif 'ERROR: The process' in err:
                        self.logger.info('T' + self.telnum + ': task already dead')
                        return True
                return True	

	# This function attempts to automatically recover the camera using 
	# increasingly drastic measures. If reconnecting, restarting maxim, 
	# power cycling the camera, and rebooting the machine don't work, it 
	# will email for help
	def recover(self):
		self.logger.warning('T' + self.telnum + ': Camera failed, beginning recovery') 
                
		# disconnect and reconnect camera
                self.disconnect_camera()
		time.sleep(5.0)
                if self.connect_camera():
                        self.logger.info('T' + self.telnum + ': Camera recovered by reconnecting') 
                        return True

		# quit and restart maxim
                self.logger.warning('T' + self.telnum + ': Camera failed to connect; quitting maxim') 
		self.quit_maxim()
                if self.connect_camera():
                        self.logger.info('T' + self.telnum + ': Camera recovered by quitting maxim') 
                        return True

		# force quit and restart maxim
                self.logger.warning('T' + self.telnum + ': Camera failed to connect; killing maxim') 
		self.quit_maxim()
		self.kill_maxim()
                if self.connect_camera():
                        self.logger.info('T' + self.telnum + ': Camera recovered by killing maxim') 
                        return True

		self.logger.info('*** camera power cycle disabled due to black box messiness ***')
#		# power cycle camera
#                self.logger.warning('T' + self.telnum + ': Camera failed to recover after restarting maxim; power cycling the camera') 
#                self.quit_maxim()
#		self.kill_maxim()
#                self.powercycle()
#                if self.connect_camera():
#                        self.logger.info('T' + self.telnum + ': Camera recovered by power cycling it') 
#                        return True

		'''
		# power cycle camera and wait longer?
                self.logger.warning('T'+self.telnum+': Camera failed to recover after power cycling the camera; trying a longer down time') 
		self.quit_maxim()
                self.powercycle(downtime=300)
                if self.connect_camera():
                        self.logger.info('T' + self.telnum + ': Camera recovered by power cycling it with a longer downtime') 
                        return True

		# power cycle camera and wait 20 minutes!
                self.logger.warning('T' + self.telnum + ': Camera failed to recover after power cycling the camera; trying a 20 minute down time') 
		self.quit_maxim()
                self.powercycle(downtime=1200)
                if self.connect_camera():
                        self.logger.info('T' + self.telnum + ': Camera recovered by power cycling it with a longer downtime') 
                        return True

		# reboot the machine???
                self.logger.warning('T' + self.telnum + 'Camera failed to recover after power cycling the camera; rebooting the machine') 
		self.quit_maxim()
                self.pdu.inst.off()
                self.send_to_computer("shutdown -s")
                time.sleep(60) # wait for it to shut down
                self.pdu.telcom.off() # turn off the computer
                self.pdu.panel.off() # turn off the telescope panel (which powers the filter wheel)
                time.sleep(300) # wait for it to discharge its capacitors
                self.pdu.telcom.on() # turn on the computer
                time.sleep(60) # wait for it to reboot
                self.pdu.inst.on() # turn on the camera
                self.pdu.panel.on() # turn on the telescope panel
                time.sleep(30) # wait for the camera to initialize

                if self.connect_camera():
                        self.logger.info('T' + self.telnum + ': Camera recovered by rebooting the machine') 
                        return True
		'''

		# I'm out of ideas; ask humans for help
		filename = self.base_directory + '/minerva_library/imager_' + self.telnum + '.error'
		while not self.connect_camera():
			mail.send("Camera on T" + self.telnum + " failed to connect",
				  "You must connect the camera and delete the file " + 
				  filename + " to restart operations.",level="serious")
			fh = open(filename,'w')
			fh.close()
			while os.path.isfile(filename):
				time.sleep(1)
		return self.connect_camera()



                
		
#test program, edit camera name to test desired camera
if __name__ == '__main__':

	if socket.gethostname() == 'Main':
        	base_directory = '/home/minerva/minerva-control'
        	config_file = 'imager_t3.ini'
        else:
                base_directory = 'C:/minerva-control/'
                config_file = 'imager_t' + socket.gethostname()[1] + '.ini'
                
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
		print ' p. restart_maxim'
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
		elif choice == 'p':
			test_imager.restartmaxim()
		elif choice == 'q':
			test_imager.recover()
		else:
			print 'invalid choice'
			
			
	
