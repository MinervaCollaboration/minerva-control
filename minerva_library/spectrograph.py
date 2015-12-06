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
import pdu

from si.client import SIClient
from si.imager import Imager
from minerva_library import dynapower
import ipdb

# spectrograph control class, control all spectrograph hardware
class spectrograph:

	def __init__(self,config, base =''):

		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.setup_logger()
		self.create_class_objects()
		self.status_lock = threading.RLock()
		self.file_name = ''
		# threading.Thread(target=self.write_status_thread).start()

   




	#load configuration file
	def load_config(self):
	
		try:
			config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.ip = config['SERVER_IP']
			self.port = int(config['SERVER_PORT'])
			self.logger_name = config['LOGNAME']
			self.exptypes = {'Template':0,
                                         'Flat':0,
                                         'Arc':0,
                                         'FiberArc': 0,
                                         'FiberFlat':0,
                                         'Bias':0,
                                         'Dark':0,
                                        }

			# reset the night at 10 am local                                                                                                 
                        today = datetime.datetime.utcnow()
                        if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                                today = today + datetime.timedelta(days=1)
                        self.night = 'n' + today.strftime('%Y%m%d')
                        self.i2positions = config['I2POSITIONS']
                        for key in self.i2positions.keys():
                                self.i2positions[key] = float(self.i2positions[key])
                        self.thar_file = config['THARFILE']
                        self.flat_file = config['FLATFILE']

		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()

	#set up logger object
	def setup_logger(self):
		
		log_path = self.base_directory + '/log/' + self.night
                if os.path.exists(log_path) == False:os.mkdir(log_path)

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
		
	def create_class_objects(self):
                #TODO Should we have this here? It makes sense to give it the time
                #TODO to warm and settle.
		self.benchpdu = pdu.pdu('apc_bench.ini',self.base_directory)
                self.cell_heater_on()
                
                
		
	#return a socket object connected to the camera server
	def connect_server(self):
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.settimeout(1)
			s.connect((self.ip, self.port))
			self.logger.info('successfully connected to spectrograph server')
		except:
			self.logger.error('failed to connect to spectrograph server')
		return s
	#send commands to camera server running on telcom that has direct control over instrument
	def send(self,msg,timeout):
		try:
			s = self.connect_server()
			s.settimeout(3)
			s.sendall(msg)
		except:
			self.logger.error("connection lost")
			self.logger.exception("connection lost")
			return 'fail'
		try:
                        self.logger.info('Timeout is '+str(timeout))
			s.settimeout(timeout)
			data = s.recv(1024)
		except:
			self.logger.error("connection timed out")
			self.logger.exception("connection timed out")
			return 'fail'
		data = repr(data).strip("'")
		if data.split()[0] == 'success':
			self.logger.info(msg.split()[0] + " command completed")
		else:
                        #ipdb.set_trace()
			self.logger.error(msg.split()[0] + " command failed")
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

        def getexpflux(self, t0):
                flux = 0.0
                with open(self.base_directory + '/log/' + self.night + '/expmeter.dat', 'r') as fh:
                        f = fh.read()
                        lines = f.split('\n')
                        for line in lines:
                                entries = line.split(',')
                                if len(entries[0]) == 26:
                                        date = datetime.datetime.strptime(entries[0], '%Y-%m-%d %H:%M:%S.%f')
                                        if date > t0: flux += float(entries[1])
                return flux
                        
		
	#start exposure
	def expose(self, exptime=1.0, exptype=0, expmeter=None):

        	host = "localhost"
                port = 2055
                client = SIClient (host, port)
                self.logger.info("Connected to SI client")

                imager = Imager(client)
                self.logger.info("Connected to SI imager")
                imager.nexp = 1		        # number of exposures
                imager.texp = exptime		# exposure time, float number
                imager.nome = "image"		# file name to be saved
                imager.dark = False		# dark frame?
                imager.frametransfer = False	# frame transfer?
                imager.getpars = False		# Get camera parameters and print on the screen

                # expose until exptime or expmeter >= flux
                t0 = datetime.datetime.utcnow()
                elapsedtime = 0.0
                flux = 0.0
                if expmeter <> None:
                        thread = threading.Thread(target=imager.do)
                        thread.start()
                        while elapsedtime < exptime:
                                time.sleep(0.1)
                                elapsedtime = (datetime.datetime.utcnow()-t0).total_seconds()
                                flux = self.getexpflux(t0)
                                self.logger.info("flux = " + str(flux))
                                if expmeter < flux:
                                        imager.retrieve_image()
                                        ## imager.interrupt()
                                        break

                        
                else:
                        imager.do()
                

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

        def recover(self):
                sys.exit()
        
	def take_image(self,exptime=1,objname='test',expmeter=None):

                exptime = int(float(exptime)) #python can't do int(s) if s is a float in a string, this is work around
		#put together file name for the image
		ndx = self.get_index()
		if ndx == -1:
			self.logger.error("Error getting the filename index")
			ipdb.set_trace()
			self.recover()
			return self.take_image(exptime=exptime, filterInd=filterInd,objname=objname,expmeter=expmeter)

		self.file_name = self.night + "." + objname + "." + str(ndx).zfill(4) + ".fits"
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
		
		if self.expose(exptime=exptime, expmeter=expmeter):
			self.logger.info('Finished taking image: ' + self.file_name)
			self.nfailed = 0 # success; reset the failed counter
			return
		else: 
        		self.logger.error('Failed to save image: ' + self.file_name)
			self.file_name = ''
			self.recover()
			return self.take_image(exptime=exptime,objname=objname,expmeter=expmeter) 

        def vent(self):
                # close the pump valve
                self.dynapower.off('pumpvalve')

                # turn off the pump
                self.dynapower.off('pump')

                if self.specgauge.pressure() < 500:
                    mail.send("The spectrograph is pumped and attempting to vent!","Manual login required to continue")
                    self.logger.error("The spectrograph is pumped and attempting to vent; manual login required to continue")
                    ipdb.set_trace()            

                # open the vent valve
                self.dynapower.on('ventvalve')

                t0 = datetime.datetime.utcnow()
                elapsedtime = 0.0
                while self.specgauge.pressure() < 500:
                    elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds() 
                    self.logger.info('Waiting for spectrograph to vent (Pressure = ' + str(specgauge.pressure()) + '; elapsed time = ' + str(elapsedtime) + ' seconds)')
                    if elapsedtime < timeout:
                        time.sleep(5)
                    else:
                        self.logger.error("Error venting the spectrograph")
                        return

                self.logger.info("Venting complete")
 
        # pump down the spectrograph (during the day)     
        def pump(self):

                timeout = 300

                # close the pump valve
                self.dynapower.off('pumpvalve')

                # turn on the pump
                self.dynapower.on('pump')

                if self.get_vacuum_pressure() > 500:
                    mail.send("The spectrograph is at atmosphere!","Manual login required to continue")
                    self.logger.error("The spectrograph is at atmosphere! Manual login required to continue")
                    ipdb.set_trace()

                # wait until the guage reads < 100 ubar
                t0 = datetime.datetime.utcnow()
                elapsedtime = 0.0
                while self.get_pump_pressure() > 100.0:
                    elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds() 
                    self.logger.info('Waiting for tube to pump down (Pressure = ' + str(pumpgauge.pressure()) + '; elapsed time = ' + str(elapsedtime) + ' seconds)')
                    if elapsedtime < timeout:
                        time.sleep(5)
                    else:
                        self.logger.error("Error pumping down the spectrograph")
                        return          
                        
                # open the pump valve
                self.dynapower.on('pumpvalve')

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
                print response
                return float(response.split()[1].split('\\')[0])

        def cell_heater_set_temp(self, temp):
                response = self.send('cell_heater_set_temp ' + str(temp),10)
                return float(response.split()[1].split('\\')[0])

        def cell_heater_get_set_temp(self):
                response = self.send('cell_heater_get_set_temp None',10)
                return float(response.split()[1].split('\\')[0]) 


	def vent(self):

		timeout = 1200.0

		# close the vent valve
		self.benchpdu.off('ventvalve')

		# close the pump valve
		self.benchpdu.off('pumpvalve')

		# turn off the pump
		self.benchpdu.off('pump')

		if self.get_spec_pressure() < 500.0:
			mail.send("The spectrograph is pumped and attempting to vent!","Manual login required to continue",level='Debug')
			self.logger.error("The spectrograph is pumped and attempting to vent; manual login required to continue")

			# TODO: make hold file to restart thread
			ipdb.set_trace()
			
		# open the vent valve                                                                                                                                                  
		self.benchpdu.on('ventvalve')

		t0 = datetime.datetime.utcnow()
		elapsedtime = 0.0
		while self.get_spec_pressure() < 500:
			elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds()
			self.logger.info('Waiting for spectrograph to vent (Pressure = ' + str(self.get_spec_pressure())\
						 + '; elapsed time = ' str(elapsedtime) + ' seconds)')

			# TODO: monitor pressure during venting and create smarter error condition                                                                                         
			if elapsedtime < timeout:
				time.sleep(5)
			else:
				self.logger.error("Error venting the spectrograph")
				return

			self.logger.info("Venting complete")


	# pump down the spectrograph (during the day)
	def pump(self):

		timeout = 1200

		if self.get_spec_pressure() > 500:
			mail.send("The spectrograph is at atmosphere!","Manual login required to continue")
			self.logger.error("The spectrograph is at atmosphere! Manual login required to continue")

			# TODO: make hold file to restart thread
			ipdb.set_trace()

		# close the vent valve 
		self.benchpdu.off('ventvalve')

		# close the pump valve
		self.benchpdu.off('pumpvalve')

		# turn on the pump
		self.benchpdu.on('pump')

		# wait until the pump gauge reads < 100 ubar
		t0 = datetime.datetime.utcnow()
		elapsedtime = 0.0
		while self.get_pump_pressure() > 0.1:
			elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds()
			self.logger.info('Waiting for tube to pump down (Pressure = ' + str(pumpgauge.pressure()) + '; elapsed time = ' str(elapsedtime) + ' seconds)')
			if elapsedtime < timeout:
				time.sleep(5)
			else:
				self.logger.error("Error pumping down the spectrograph")
				return

		# open the pump valve
		self.benchpdu.on('pumpvalve')
		self.logger.info("Pumping down the spectrograph")
		# TODO: wait for pressure to go below some value??    

	# close the valves, hold the pressure (during the night)
	def hold(self):
		# make sure the vent valve is closed
		self.benchpdu.off('ventvalve')
		# close the pump valve
		self.benchpdu.off('pumpvalve')
		# turn off the pump        
		self.benchpdu.off('pump')

			
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

        #S Query the position of the i2stage. 
        #S response is 'success '+str(position)
        def i2stage_get_pos(self):
                response = self.send('i2stage_get_pos None',10)
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

        #S This is used to check how long the lamp has been turned on for
        #S from the LAST time it was turned on, not total time on. Used
        #S for equipment checks in control.py, so needed to send to
        #S the server.
        def time_tracker_check(self,filename):
                response = self.send("time_tracker_check "+filename,10)
                return float(response.split()[1].split('\\')[0])
        
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
        

        
	
if __name__ == '__main__':
	
	base_directory = '/home/minerva/minerva-control'
        if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	test_spectrograph = spectrograph('spectrograph.ini',base_directory)
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
			test_spectrograph.expose()
		elif choice == 'c':
			test_spectrograph.set_data_path()
		elif choice == 'd':
			test_spectrograph.set_binning()
		elif choice == 'e':
			test_spectrograph.set_size()
		elif choice == 'f':
			test_spectrograph.settle_temp()
		elif choice == 'g':
			print test_spectrograph.get_vacuum_pressure()
		elif choice == 'h':
			print test_spectrograph.get_atmospheric_pressure()
		else:
			print 'invalid choice'
			
			
	
