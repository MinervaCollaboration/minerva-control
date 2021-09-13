import socket
import logging
import threading
from configobj import ConfigObj
import sys, ipdb
import com
import os
import time
import glob
import datetime
import pyfits
import shutil
import json
import collections
import struct
from PyAPT import APTMotor
import subprocess
import win32api
import atexit
import re
import json
import numpy as np
import pdu
import mail
import math
import utils
import dynamixel

# minerva library dependency
#S Put copy of dynapwoer.py in spectrograph_modules for power stuff on expmeter
import spectrograph_modules

sys.dont_write_bytecode = True

class server:
        
	#initialize class
	def __init__(self,name,base):
                #S Name is an agruement.
		self.name = name
		#S Arguement again
		self.base_directory = base
		self.data_path_base = "C:\minerva\data"
		#S Defined later
                self.load_config()

                #S Defined later.
                self.setup_logger()
                self.logger_lock = threading.Lock()
                #S Defined later.
#                self.set_data_path()
                self.file_name = ''
                #S Create all class objects
                self.create_class_objects()
                # self.chiller = com.com('chiller',self.base_directory,self.night())
                self.logger.warning('chiller disabled')
                self.chillerlastemailed = datetime.datetime.utcnow() - datetime.timedelta(days=1)

                # turn on cell heater to maintain temperature stablility
                self.cell_heater_on()

                self.nspecfail = 0
                self.lastemailed = datetime.datetime.utcnow() - datetime.timedelta(days=1)
		self.backlightonrequest = datetime.datetime.utcnow() - datetime.timedelta(days=1)

                #S Set up closing procedures
                win32api.SetConsoleCtrlHandler(self.safe_close,True)
                atexit.register(self.safe_close,'signal_arguement')
        #S Used in the initialization.
	def load_config(self):
                #S Finds the config file.
		configfile = self.base_directory + '/config/spectrograph_server.ini'
		#S Tries all the configuration materials. 
		try:
        		config = ConfigObj(configfile)
			self.port = int(config['PORT'])
			self.ip = config['HOST']
                        self.logger_name = config['LOGNAME']
			self.pdu_config = config['PDUCONFIG']
                        self.header_buffer = ''
                        self.thar_file = config['THARFILE']
                        self.flat_file = config['FLATFILE']
                        self.i2serial = int(config['I2SERIAL'])
                        self.i2hwtype = int(config['I2HWTYPE'])
                        self.i2positions = config['I2POSITIONS']
                        self.log_exposure_meter = True
                        for key in self.i2positions.keys():
                                self.i2positions[key] = float(self.i2positions[key])
		except:
			print('ERROR accessing ', self.name, ".", 
				   self.name, " was not found in the configuration file", configfile)
			return 

        def night(self):
		return 'n' + datetime.datetime.utcnow().strftime('%Y%m%d')
	
	#create logger object and link to log file
	def setup_logger(self):
                #S Looks for existing log path, and creates one if none exist.
		log_path = self.base_directory + '\\log\\' + self.night()
		
                if os.path.exists(log_path) == False:
                        os.mkdir(log_path)

		self.logger = utils.setup_logger(self.base_directory,self.night(),self.logger_name)

	def data_path(self):
                data_path = self.data_path_base + '\\' + self.night()
		if not os.path.exists(data_path):
			os.mkdir(data_path)
		return data_path
	
        #S Finds path for data, creates if none exist. What is the point of the
	#S night arguement though? Doesn;t go into self., as that's defined
	#S earlier.
#	def set_data_path(self):
#		self.data_path = self.data_path_base + '\\' + self.night()
#		if not os.path.exists(self.data_path):
#			os.makedirs(self.data_path)
#		return 'success'

	#S Create class objects
	def create_class_objects(self):
                #S I would home here, or maybe it would be better to put it in the self.i2stage_connect()?
                #S I would say it makes sense to put in the the stage connect
                
		self.pdu = pdu.pdu(self.pdu_config, self.base_directory)
                self.gaugeController = com.com('gaugeController',self.base_directory,self.night())    
                self.cellheater_com = com.com('I2Heater',self.base_directory,self.night())                
                self.expmeter_com = com.com('expmeter',self.base_directory,self.night())    
                self.backlight_com = com.com('backlight',self.base_directory,self.night())
                dyn = dynamixel.USB2Dynamixel_Device('COM7')
                self.backlight_motor = dynamixel.Robotis_Servo2(dyn, 1, series = "XM" )
                self.benchpdu = pdu.pdu('apc_bench.ini',self.base_directory)
		self.controlroompdu = pdu.pdu('apc_5.ini',self.base_directory)
                self.i2stage_connect()
		
                return



#==================server functions===================#
#used to process communication between camera client and server==#

	#process received command from client program, and send response to given socket object
	def process_command(self, command, conn):
		command = command.strip("'")
		tokens = command.split(None,1)
		if len(tokens) != 2:
			response = 'fail'
		elif tokens[0] == 'cell_heater_on':
                        response = self.cell_heater_on()
                elif tokens[0] == 'cell_heater_off':
                        response = self.cell_heater_off()
                elif tokens[0] == 'cell_heater_temp':
                        response = self.cell_heater_temp()
                elif tokens[0] == 'cell_heater_set_temp':
                        response = self.cell_heater_set_temp(tokens[1])
                elif tokens[0] == 'cell_heater_get_set_temp':
                        response = self.cell_heater_get_set_temp()                        
                elif tokens[0] == 'get_spec_pressure':
                        response = self.get_spec_pressure()
                elif tokens[0] == 'get_pump_pressure':
                        response = self.get_pump_pressure()
		elif tokens[0] == 'get_filter_name':
			response = self.get_filter_name(tokens[1])
		elif tokens[0] == 'expose':
			response = self.expose(tokens[1])
		elif tokens[0] == 'set_camera_param':
			response = self.set_camera_param(tokens[1])
		elif tokens[0] == 'set_data_path':
			response = self.set_data_path()
		elif tokens[0] == 'get_status':
			response = self.get_status(tokens[1])
		elif tokens[0] == 'get_fits_header':
			response = self.get_fits_header(tokens[1])
		elif tokens[0] == 'get_index':
			response = self.get_index(tokens[1])
		elif tokens[0] == 'save_image':
			response = self.save_image()
		elif tokens[0] == 'set_binning':
			response = self.set_binning(tokens[1])
		elif tokens[0] == 'set_file_name':
			response = self.set_file_name(tokens[1])
		elif tokens[0] == 'set_size':
			response = self.set_size(tokens[1])
		elif tokens[0] == 'write_header':
			response = self.write_header(tokens[1])
		elif tokens[0] == 'write_header_done':
			response = self.write_header_done(tokens[1])
		elif tokens[0] == 'i2stage_connect':
			response = self.i2stage_connect()
		elif tokens[0] == 'i2stage_disconnect':
			response = self.i2stage_disconnect()
		elif tokens[0] == 'i2stage_get_pos':
			response = self.i2stage_get_pos()
		elif tokens[0] == 'i2stage_home':
			response = self.i2stage_home()
		elif tokens[0] == 'i2stage_move':
			response = self.i2stage_move(tokens[1])
		elif tokens[0] == 'i2stage_movef':
			response = self.i2stage_movef(float(tokens[1]))
		elif tokens[0] == 'thar_turn_on':
			response = self.thar_turn_on()
		elif tokens[0] == 'thar_turn_off':
			response = self.thar_turn_off()
		elif tokens[0] == 'flat_turn_on':
			response = self.flat_turn_on()
		elif tokens[0] == 'flat_turn_off':
			response = self.flat_turn_off()
		elif tokens[0] == 'led_turn_on':
			response = self.led_turn_on()
		elif tokens[0] == 'led_turn_off':
			response = self.led_turn_off()
		elif tokens[0] == 'time_tracker_check':
                        response = self.time_tracker_check(tokens[1])
		elif tokens[0] == 'stop_log_expmeter':
			response = self.stop_log_expmeter()
		elif tokens[0] == 'start_log_expmeter':
			response = self.start_log_expmeter()
		elif tokens[0] == 'start_si_image':
                        response = self.start_si_image()
                elif tokens[0] == 'kill_si_image':
                        response = self.kill_si_image()
                elif tokens[0] == 'get_expmeter_total':
                        response = self.get_expmeter_total()
                elif tokens[0] == 'reset_expmeter_total':
                        response = self.reset_expmeter_total()
                elif tokens[0] == 'backlight_on':
                        response = self.backlight_on()
                elif tokens[0] == 'backlight_off':
                        response = self.backlight_off()
#                elif tokens[0] == 'update_dynapower1':
#                        response = self.update_dynapower1()
#                elif tokens[0] == 'update_dynapower2':
#                        response = self.update_dynapower2()
		
		else:
			response = 'fail'
			self.logger.error(tokens[0]+' got to fail')
			
		try:
			conn.settimeout(3)
			conn.sendall(response)
			conn.close()
		except:
                        self.logger.exception('failed to send response, connection lost')
			self.logger.error('failed to send response, connection lost')
			return

		if response.split()[0] == 'fail':
			self.logger.info('command failed: (' + tokens[0] +')')
		else:
			self.logger.info('command succeeded(' + tokens[0] +')')
			

	def update_logpaths(self,path):
		self.logger.info('Updating log paths!')
		
		if not os.path.exists(path): os.mkdir(path)
		
		fmt = "%(asctime)s [%(filename)s:%(lineno)s,%(thread)d - %(funcName)s()] %(levelname)s: %(message)s"
		datefmt = "%Y-%m-%dT%H:%M:%S"
		formatter = logging.Formatter(fmt,datefmt=datefmt)
		formatter.converter = time.gmtime
		
                self.logger_lock.acquire()

		for fh in self.logger.handlers: self.logger.removeHandler(fh)
		fh = logging.FileHandler(path + '/' + self.logger_name + '.log', mode='a')
                fh.setFormatter(formatter)
		self.logger.addHandler(fh)

                self.logger_lock.release()

	def logpath_watch(self):
                lastnight = ''
                #S update the logger, similar to in domeControl
		while True:
                        t0 = datetime.datetime.utcnow()
			
                        # roll over the logs to a new day                                                                                                                   
                        thisnight = datetime.datetime.strftime(t0,'n%Y%m%d')
                        if thisnight != lastnight:
                                self.update_logpaths(self.base_directory + '/log/' + thisnight)
                                lastnight = thisnight
                                
                        #S sleep until tomorrow
                        tomorrow = datetime.datetime.replace(t0 + datetime.timedelta(days=1),hour=0,minute=0,second=0)
                        tomorrow_wait = (tomorrow - t0).total_seconds()
                        sleep_time = max(1.,0.99*tomorrow_wait)
                        self.logger.info('Waiting %.2f to update log paths'%(sleep_time))
                        time.sleep(sleep_time)

        def start_si_image(self):
                #S not sure how big of a deal formatting is for this, or how putting it in the .ini would be,
                #S but it works now, so leaving as is. Same for the kill command
                try:
                        siexe = r"C:/Program Files/SI Image SGL Rev E/SI Image SGL E_64.exe"
                        subprocess.Popen([siexe],shell=True,stdin=None,stdout=None,stderr=None,close_fds=True)
                        self.logger.info('Started SI Image')
                        return 'success'
                except:
                        self.logger.exception('Failed to start SI Image')
                        return 'fail'
                                

        def kill_si_image(self):
                try:
                        killer = r'taskkill /IM "SI Image SGL E_64.exe" /f'
                        subprocess.Popen(killer)#,shell=True,stdin=None,stdout=None,stderr=None)
                        self.logger.info('Successfully killed SI Image')
                        return 'success'
                except:
                        self.logger.info('Failed to kill SI Image?')
                        return 'fail'
		
			
	#server loop that runs indefinitely and handle communication with client
	def run_server(self):
		##ipdb.set_trace()
		
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind((self.ip, self.port))
                s.listen(True)
                ##s.settimeout(1)#S
                while True:

                        print 'listening to incoming connection on port ' + str(self.port)
                        #S Conn is a new secket object created by s.accept(), where
                        #S addr is he address where the socket is bound to. 
                        conn, addr = s.accept()
                        try:
                                conn.settimeout(3)
                                data = conn.recv(1024)
                        except:
                                break
                        if not data:break
                        self.process_command(repr(data),conn)
                conn.close()
                s.close()
                self.run_server()

        def chiller_status_dict(self):

                status_dict = {}
                status = self.get_chiller_status()
                if status != 'fail':
                        status = int(float(status.split()[1]))
                        status_dict['run']                    = bool(status & 0x000000001)
                        status_dict['remote_lock']            = bool(status & 0b000000010)
                        status_dict['ready']                  = bool(status & 0b000000100)
                        status_dict['less_than_set_point']    = bool(status & 0b000001000)
                        status_dict['greater_than_set_point'] = bool(status & 0b000010000)
                        status_dict['tec_heating']            = bool(status & 0b000100000)
                        status_dict['general_warning']        = bool(status & 0b001000000)
                        status_dict['general_alarm']          = bool(status & 0b010000000)
                        status_dict['autotune']               = bool(status & 0b100000000)

                faults = self.get_chiller_faults()
                if faults != 'fail':
                        faults = int(float(faults.split()[1]))
                        status_dict['rtd']       = bool(faults & 0b0001)
                        status_dict['tank_low']  = bool(faults & 0b0010)
                        status_dict['pump_fail'] = bool(faults & 0b0100)
                        status_dict['fan_fail']  = bool(faults & 0b1000)
                return status_dict

        def get_chiller_status(self):
                try:
                        status = float(self.chiller.send('STAT1A?'))
                except:
                        self.logger.exception("Unexpected response: " + response)
                        return 'fail'
                return 'success ' + str(status)

        def get_chiller_faults(self):
                try:
                        faults = float(self.chiller.send('FLTS1A?'))
                except:
                        self.logger.exception("Unexpected response: " + response)
                        return 'fail'
                return 'success ' + str(faults) 

        def get_chiller_temp(self):
                try:
                        temp = float(self.chiller.send('TEMP?'))
                except:
                        self.logger.exception("Unexpected response: " + response)
                        return 'fail'
                return 'success ' + str(temp)
        def get_chiller_settemp(self):
                try:
                        temp = float(self.chiller.send('SETTEMP?'))
                except:
                        self.logger.exception("Unexpected response: " + temp)
                        return 'fail'
                return 'success ' + str(temp)
        def get_chiller_pumptemp(self):
                try:
                        temp = float(self.chiller.send('PUMPTEMP?'))
                except:
                        self.logger.exception("Unexpected response: " + temp)
                        return 'fail'
                return 'success ' + str(temp)

	def logchiller(self):
                while True:
                        t0 = datetime.datetime.utcnow()
                        path = self.base_directory + "/log/" + self.night() + "/"
                        if not os.path.exists(path): os.mkdir(path)
                        status = self.chiller_status_dict()

                        # watch dog for chiller failures
			if 'rtd' in status.keys():
                                if status['rtd'] and (datetime.datetime.utcnow() - self.chillerlastemailed).total_seconds() > 86400:
                                        mail.send("Chiller RTD failed",
                                                  "Dear Benevolent Humans,\n\n"+
                                                  "The chiller's RTD failed. Please investigate.\n\n"
                                                  "Love,\nMINERVA",level="serious")
                                        self.chillerlastemailed = datetime.datetime.utcnow()
			if 'fan_fail' in status.keys():
                                if status['fan_fail'] and (datetime.datetime.utcnow() - self.chillerlastemailed).total_seconds() > 86400:
                                        mail.send("Chiller fan failed",
                                                  "Dear Benevolent Humans,\n\n"+
                                                  "The chiller's fan failed. Please investigate.\n\n"
                                                  "Love,\nMINERVA",level="serious")
                                        self.chillerlastemailed = datetime.datetime.utcnow()
			if 'pump_fail' in status.keys():
                                if status['pump_fail'] and (datetime.datetime.utcnow() - self.chillerlastemailed).total_seconds() > 86400:
                                        mail.send("Chiller pump failed",
                                        	  "Dear Benevolent Humans,\n\n"+
                                        	  "The chiller's pump failed. Please investigate.\n\n"
                                        	  "Love,\nMINERVA",level="serious")
                                        self.chillerlastemailed = datetime.datetime.utcnow()
			if 'tank_low' in status.keys():
                                if status['tank_low'] and (datetime.datetime.utcnow() - self.chillerlastemailed).total_seconds() > 86400:
                                        mail.send("Chiller tank level is low",
                                                  "Dear Benevolent Humans,\n\n"+
                                                  "The chiller's tank level is low. Please fill.\n\n"
                                                  "Love,\nMINERVA",level="serious")
                                        self.chillerlastemailed = datetime.datetime.utcnow()                        
                        
			# get the pressure in the spectrograph
                        with open(path + 'chiller_temps.log','a') as fh:
                                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
                                response = self.get_chiller_temp()
                                if response <> 'fail': temp = str(response.split()[1])
                                else: temp = 'UNKNOWN'
                                        
                                response = self.get_chiller_settemp()
                                if response <> 'fail': settemp = str(response.split()[1])
                                else: settemp = 'UNKNOWN'

                                response = self.get_chiller_pumptemp()
                                if response <> 'fail': pumptemp = str(response.split()[1])
                                else: pumptemp = 'UNKNOWN'
                                fh.write('%s,%s,%s,%s\n'%(now,temp, settemp, pumptemp))
                        sleeptime = 5.0 - (datetime.datetime.utcnow() - t0).total_seconds()
                        if sleeptime > 0.0: time.sleep(sleeptime)
                return          

        def set_file_name(self,param):
                if len(param.split()) != 1:
			self.logger.error('parameter mismatch')
			return 'fail'
		self.logger.info('setting name to:' + param)
		self.file_name = self.data_path() + '\\' + param                
                return 'success'
		
	def save_image(self):

		self.logger.info('saving image to:' + self.file_name)

                try:
                        #shutil.copy("C:/IMAGES/I","C:/minerva/data/n20151211/I10.fits")
                        shutil.move("C:/IMAGES/I",self.file_name)
                        return 'success'
		except: return 'fail'

        def get_index(self,param):
                files = glob.glob(self.data_path() + "/*.fits")
                return 'success ' + str(len(files)+1)
		
	def write_header(self,param):		
		self.header_buffer = self.header_buffer + param
		return 'success'
		
	def write_header_done(self,param):

                self.logger.info("here")

		try: 
			self.logger.info("Writing header for " + self.file_name)
		except: 
			self.logger.error("self.file_name not defined; saving failed earlier")
			self.logger.exception("self.file_name not defined; saving failed earlier")
			return 'fail'

		try:
			header_info = self.header_buffer + param
			self.header_buffer = ''
                        self.logger.debug("filename = " + self.file_name)
			
			f = pyfits.open(self.file_name, mode='update')
			for key,value in json.loads(header_info,object_pairs_hook=collections.OrderedDict).iteritems():
				if isinstance(value, (str, unicode)):
					f[0].header[key] = value
				else:
					if isinstance(value[0],float):
						if math.isnan(value[0]): f[0].header[key] = ('NaN',value[1])
						else: f[0].header[key] = (value[0],value[1])
					else: f[0].header[key] = (value[0],value[1])

			# convert DATE-OBS from local time to UTC
			fmt = '%Y-%m-%dT%H:%M:%S.%f'
			dateobs = (datetime.datetime.strptime(f[0].header['DATE-OBS'],fmt) + datetime.timedelta(hours=7)).strftime(fmt)[:-3]

			f[0].header['DATE-OBS'] = (dateobs,"UTC at exposure start")
                        f[0].header['JD'] = utils.dateobs2jd(dateobs)
                        f[0].header['MEXPTIME'] = float(f[0].header['PARAM24'])/1000.0
                        startstop = f[0].header['TIME'].split()
                        starttime = datetime.datetime.strptime(startstop[0],"%H:%M:%S.%f")
                        endtime = datetime.datetime.strptime(startstop[2],"%H:%M:%S.%f")
                        exptime = (endtime-starttime).total_seconds()
                        if starttime > endtime: exptime += 86400.0 # handle the exposure stradling midnight
                        f[0].header['EXPTIME'] = exptime
                        f[0].header['SET-TEMP'] = float(f[0].header.comments['PARAM62'].split('(')[1].split('C')[0].strip())
                        f[0].header['CCD-TEMP'] = float(f[0].header['PARAM0'])
                        f[0].header['BACKTEMP'] = float(f[0].header['PARAM1'])
                        f[0].header['XBINNING'] = float(f[0].header['PARAM18'])
                        f[0].header['YBINNING'] = float(f[0].header['PARAM22'])
                        f[0].header['XORGSUBF'] = float(f[0].header['PARAM16'])
                        f[0].header['YORGSUBF'] = float(f[0].header['PARAM20'])
                        f[0].header['SHUTTER'] = f[0].header.comments['PARAM8'].split('(')[-1].split(")")[0].strip()
                        f[0].header['XIRQA'] = f[0].header.comments['PARAM9'].split('(')[-1].split(")")[0].strip()
                        f[0].header['COOLER'] = f[0].header.comments['PARAM10'].split('(')[-1].split(")")[0].strip()
                        f[0].header['CONCLEAR'] = f[0].header.comments['PARAM25'].split('(')[-1].split(")")[0].strip()
                        f[0].header['DSISAMP'] = f[0].header.comments['PARAM26'].split('(')[-1].split(")")[0].strip()
                        f[0].header['ANLGATT'] = f[0].header.comments['PARAM27'].split('(')[-1].split(")")[0].strip()
                        f[0].header['PORT1OFF'] = f[0].header['PARAM28']
                        f[0].header['PORT2OFF'] = f[0].header['PARAM29']
                        f[0].header['TDIDELAY'] = f[0].header['PARAM32']
                        f[0].header['CMDTRIG'] = f[0].header.comments['PARAM39'].split('(')[-1].split(")")[0].strip()
                        f[0].header['ADCOFF1'] = f[0].header['PARAM44']
                        f[0].header['ADCOFF2'] = f[0].header['PARAM45']
                        f[0].header['MODEL'] = f[0].header['PARAM48']
                        f[0].header['HWREV'] = f[0].header['PARAM50']
                        f[0].header['SERIALP'] = f[0].header.comments['PARAM51'].split('(')[-1].split(")")[0].strip()
                        f[0].header['SERIALSP'] = f[0].header.comments['PARAM52'].split('(')[-1].split(")")[0].strip()
                        f[0].header['SERIALS'] = f[0].header['PARAM53']
                        f[0].header['PARALP'] = f[0].header.comments['PARAM54'].split('(')[-1].split(")")[0].strip()
                        f[0].header['PARALSP'] = f[0].header.comments['PARAM55'].split('(')[-1].split(")")[0].strip()
                        f[0].header['PARALS'] = f[0].header['PARAM56']
                        f[0].header['PARDLY'] = f[0].header['PARAM57']
                        f[0].header['NPORTS'] = f[0].header.comments['PARAM58'].split('(')[-1].split(" ")[0].strip()
                        f[0].header['SHUTDLY'] = f[0].header['PARAM59']

                        del f[0].header['N_PARAM']
                        del f[0].header['DATE']
                        del f[0].header['TIME']
                        for i in range(80): del f[0].header['PARAM' + str(i)]
                        del f[0].header['NAXIS3']

                        # recast as 16 signed integer (2x smaller with no loss of information)
#                        # FITS standard uses "two's complement" => signed int = unsigned int
#                        f[0].data = np.invert(f[0].data) 
#                        f[0].data = f[0].data.astype('uint16')
#                        f[0].data = f[0].data.astype('int16')

			f.flush()
			f.close()

			return 'success'

		except:
			self.logger.error("failed to create header")
			self.logger.exception("failed to create header")
			return 'fail'
		return 'success'

        ###
        # LED for backlighting fiber
        ###
        def backlight_on(self):
		self.backlightonrequest = datetime.datetime.utcnow()
                self.backlight_move_motor(-45)
                time.sleep(0.1)
                self.backlight_com.send('n8')

		# failsafe so backlight doesn't stay on
		# backlight creates heat that disrupts the thermal stability of the spectrograph!!
		backlight_failsafe_thread = threading.Thread(target = self.backlight_failsafe)
		backlight_failsafe_thread.name = 'Kiwispec'
		backlight_failsafe_thread.start()

                return 'success'

        def backlight_off(self):
                self.backlight_com.send('f8')
                self.backlight_move_motor(-90)
                return 'success'

	# a failsafe so the backlight doesn't stay on
	# called by backlight_on in a separate thread
	def backlight_failsafe(self, timeout=60):
		t0 = datetime.datetime.utcnow()
		timeElapsed = 0
		while timeElapsed < timeout:
			timeElapsed = (datetime.datetime.utcnow() - t0).total_seconds()
			if (datetime.datetime.utcnow() - self.backlightonrequest).total_seconds() > timeout:
				self.logger.error("encountered failsafe; turning off the backlight")
				self.backlight_off()
				return
			time.sleep(1)

        ###
        # Dynamixel motor
        ###
        def backlight_move_motor(self,position):
                self.backlight_motor.disable_torque()
                self.backlight_motor.protocol2_write_address( 11, [3])
                self.backlight_motor.enable_torque()
                self.backlight_motor.move_angle(math.radians(position))
                if position == -90:
                        time.sleep(0.25)
                        self.backlight_motor.disable_torque()

        ###
        # THORLABS STAGE, For Iodine Cell, i2stage, i2motor
        ###


        #S Initialize the stage, needs to happen before anyhting else.
        def i2stage_connect(self):

                #S Decided to place a power cycle before any connection we make to the i2stage.
                #S There is an issue that occurs in a dynamic linked librry (.dll) file that PyAPT uses
                #S if the motor was not discnnected properly. If the issue is hit, it crashes python.exe,
                #S and will do so until the power is cycled on the motor. So, to try and avoid this as uch
                #S as possible, a power cycle is being included. The ten second sleep time is there to give
                #S the motor some time to do it's start up stuff (e.g. it won't connect if you try to
                #S quickly after the cycle.

                # NOTE: the home position must be away from the motor. Otherwise homing will timeout
                self.benchpdu.i2stage.off()
                time.sleep(10)
                self.benchpdu.i2stage.on()
                time.sleep(10)                
                
                #S Try and connect and initialize
                try:
                        #S Connect the motor with credentials above.
                        #ipdb.set_trace()
                        self.motorI2 = APTMotor(SerialNum=self.i2serial , HWTYPE=self.i2hwtype)
                        #S Initialize motor, we can move and get info with this.
                        #S Can't be controllecd by anything else until relesased.
                        #S NOTE this is actually included in APTMotor routine, so commenting out.
                        ## self.motorI2.initializeHardwareDevice()
                        #S Get curtrent position, needed for logging?
                        ## currentPos = self.motorI2.getPos()
                        #S Write it down, commented out for now.
                        ## self.logger.info("Iodine stage connected and initialized. Started at position: %0.5f mm"%(currentPos))

                        #S Location str fot header, unknown because just started.
                        self.motorI2.lastlocationstr = 'unknown'
                        
                #S Something goes wrong. Remember, only one application can connect at
                #S a time, e.g. Kiwispec but not *.py
                except Exception as e:
                        print e
                        self.logger.error("ERROR: did not connect to the Iodine stage.")
                        return 'fail'

                # home the stage then move to the nominal (in) position
                self.logger.info("Iodine stage connected; homing")
                self.i2stage_home()
                self.logger.info("Iodine cell homed, moving to 'OUT' position, needs to be changed to 'IN'")
                self.i2stage_move('out')
                self.logger.info("Iodine cell homed, moving to 'in' position")
                self.i2stage_move('in')
        
                return 'success'
        #S Disconnect gracefully from Iodine stage. Not sure if we want to log last position
        #S as I don't see a need for it, but just uncomment sections to do so. Included a try:
        #S incase the stage was never connected, as this function will be included in
        #S ConsoleCtrlHandler().
        def i2stage_disconnect(self):
                try:
                        #currentPos = self.motorI2.getPos()
                        self.motorI2.cleanUpAPT()
                        #S Logging of succesful left off for now
                        ## self.logger.info("Iodine stage diconnected and cleaned up.")# Left as position: %0.5f mm"%(currentPos))
                except:
                        #? Does this deserve an error?
                        self.logger.error("ERROR: The Iodine stage was never connected, or something else went wrong")
                return 'success'

	def i2stage_home(self):
		try:
                        self.motorI2.mAbs(0)
                except:
                        #throw and log error on bad position
                        self.logger.exception("ERROR: Iodine failed to move.")
                        return 'fail'
                try:
			self.motorI2.go_home()
                        return 'success'
		except ValueError as e:
                        # Bug in the pyAPT dll causes an exception here, but it's successful
                        self.logger.info('Successfully homed iodine stage')
			return 'success'
		except:
                        self.logger.exception('Failed to home, unexpected error')
                        return 'fail'
                return 'success'

        #S Get the position of the I2 stage
        def i2stage_get_pos(self):
                try:
                        #S Query position
                        current_pos = self.motorI2.getPos()
                        #S We also want to math this to a position string.
                        #S We always assign it the unknown string first, then it has to be
                        #S matched to be given an actual location string. Mathcing is rounded
                        #S to tenthes of a millimeter.
                        locationstr = 'unknown'
                        for key in self.i2positions.keys():
                                if round(current_pos,1) == self.i2positions[key]:
                                        locationstr = key
                        return 'success ' + str(current_pos) + ' ' +locationstr
                except:
                        self.logger.error("The Iodine stage isn't connected (most likely).")
			return 'fail'
        

        #S Move the stage around, needs to be initialized first
        #? Do we need to worry about max velocities or anyhting?
        def i2stage_move(self, locationstr):
                #S Last set location string, for header info
                self.motorI2.lastlocationstr = locationstr

                #S Get previous position
                prev_pos = self.motorI2.getPos()

                #S Try to get locationstr from dictionary in config.
                try:                       
                        i2stage_move_thread = threading.Thread(target = self.motorI2.mAbs, args = (self.i2positions[locationstr.lower()],))
			i2stage_move_thread.name = 'Kiwispec'
                        i2stage_move_thread.start()
                        #S need to log position, stuff, anything else?
                        self.logger.info("Iodine stage moving from %0.5f mm to %0.5f mm"%(prev_pos,self.i2positions[locationstr.lower()]))
                        return 'success'
                except:
                        #throw and log error on bad position
                        self.logger.error("ERROR: Iodine failed to move or invalid location (" + locationstr+ ")")
                        return 'fail'
                        

        #S Move the stage around, needs to be initialized first
        #? Do we need to worry about max velocities or anyhting?
        def i2stage_movef(self, position):

                if position < 0.0 or position > 150.0:
                #if position < -150.0 or position > 0.0:
                        self.logger.error("Requested position out of range")
                        return "fail"

                #S Get previous position
                prev_pos = self.motorI2.getPos()

                #S Try to get locationstr from dictionary in config.
                try:                       
                        i2stage_move_thread = threading.Thread(target = self.motorI2.mAbs, args = (position,))
                        i2stage_move_thread.name = 'Kiwispec'
                        i2stage_move_thread.start()
                        #S need to log position, stuff, anything else?
                        self.logger.info("Iodine stage moving from %0.5f mm to %0.5f mm"%(prev_pos,position))
                        return 'success'
                except:
                        #throw and log error on bad position
                        self.logger.error("ERROR: Iodine failed to move or invalid location.")
                        return 'fail'



        ###
	# CELL HEATER FUNCTIONS/COMMANDS, cellheater, cell_heater
	###

        #S Get the cell heater's status, used in a lot of the other functions. Returns
	#S some good and some useless information. 
        def cell_heater_status(self):
                #S Get the status from the heater
                statusstr = self.cellheater_com.send("stat?")
                #S This function grabs all numbers in the string. Found
                #S online, and super interesting. Need to look into more.
                #S Read how it works, and understand it. It's dope. Returns a
                #S list of strings of the instances of numbers, and weonly want
                #S one, thus the index.
                hexstr = re.findall('[-+]?\d+[\.]?\d*',statusstr)[0]
                #S Conversion from hex to binary string. Added a padding '1'
                #S to ensure all leading zeros are kept. Also reverse order
                #S the string to put the zeroeth bit in the zeroeth
                #S position of the string array. Shaved off with [3:0],
                #S by that I mean leading one and conversion stuff on the front.
                binstr = bin(int('1'+hexstr,16))[3:][::-1]
                #S Now we have a sbinary number in string form, we'll
                #S extract it's info and feed 'status'.
                '''
                Bit 0 0 = Disabled, 1 = Enabled
                Bit 1 0 = Normal Mode, 1 = Cycle Mode
                Bit 2 0 = TH10K, 1 = PTC100 (sensor select bit one)
                Bit 3 0 = See Bit2, 1 = PTC1000 (sensor select bit two)
                Bit 4 0 = See Bit5, 1 = degrees C (unit select bit one)
                Bit 5 0 = Degrees K, 1 = Degrees F (unit select bit two)
                Bit 6 0 = No Sensor Alarm, 1 = Sensor Alarm
                Bit 7 0 = Cycle Not Paused, 1 = Cycle Paused
                '''
    
                #S Converting bits in binstr to boolean for the the status
                #S dictionary.
                status = {}
                status['enabled'] = bool(int(binstr[0]))
                status['cyclemode'] = bool(int(binstr[1]))
                status['PTC100'] = bool(int(binstr[2]))
                status['PTC1000'] = bool(int(binstr[3]))
                #S Using bits four and five to figure the units on the machine.
                #S See docstring above and follow logic..
                if bool(int(binstr[4])):
                        unit = "C"
                else:
                        if bool(int(binstr[5])):
                                unit = "F"
                        else:
                                unit = "K"
                status['unit'] = unit
                status['alarm'] = bool(int(binstr[6]))
                status['paused'] = bool(int(binstr[7]))

                #S Returns the status dictionary.
                return status
        
        #S Turn the heater on, uses the status of the heater.
        def cell_heater_on(self):
                #S Get the current status of the heater  
                status = self.cell_heater_status()
                #S If it was off, we'll turn it on. Checked status due to toggle nature of heater power.
                if not status['enabled']:
                        self.logger.info("Cell heater off; turning on")
                        self.cellheater_com.send("ens")
                #S It was already on, so no worries.   
                else:
                        self.logger.info("Cell heater already on")
                #S We did it!
                return 'success'
        
        #S You guessed it, turns the heater off.
        def cell_heater_off(self):
                #S Get the currrent status of the cell heater
                status = self.cell_heater_status()
                #S Check if already off or on, due to fact that we can only toggle.
                #S If it's on, turn it off!
                if status['enabled']:
                        #S Log that is was on.
                        self.logger.info("Cell heater on; turning off")
                        #S Actually turn it off.
                        self.cellheater_com.send("ens")
                #S Already off, so no worries
                else:
                        self.logger.info("Cell heater already off")
                #S We succeeded
                return 'success'
        
        #S The current actualy temperature of the heater. Uses status to 
        #S determine whether the heater is on or not.
        def cell_heater_temp(self):
                #S Status for units, check if on
                status = self.cell_heater_status()
                self.logger.info('Cell heater in get temp is '+str(status['enabled']))
                #S Gets that temp
                tempstr = self.cellheater_com.send("tact?")
                #S Finds the number in the returned string from 'tact?'
                actual_temp = re.findall('[-+]?\d+[\.]?\d*',tempstr)[0]
                #S Is the heater on or off, and logs accordingly.
                if status['enabled']:
                        self.logger.info("Cell heater is on and at "+actual_temp+" C")
                else:
                        self.logger.info("Cell heater is off and at "+actual_temp+" C")
                        
                returnstr =  "success " + actual_temp +" C"
                self.logger.info(returnstr)
                return returnstr
        
        #S Sets the temperature for the heater to aim for.       
        def cell_heater_set_temp(self, temp):
                #S Despite not asking for a return, we still get one. Used
                #S to confirm that the set temperature recorded is that from the
                #S heater itself.
                newsetstr = self.cellheater_com.send('tset='+str(temp))
                new_set_temp = re.findall('[-+]?\d+[\.]?\d*',newsetstr)[0]
                #S Don't forget to log!
                self.logger.info('Cell heater temp has been set to '+new_set_temp+' C')
                #S return with units from status
                return 'success '+new_set_temp+' C'
        
        #S Query the set temperature.       
        def cell_heater_get_set_temp(self):
                #S Actual query
                setstr = self.cellheater_com.send('tset?')
                #S Parse for number
                set_temp = re.findall('[-+]?\d+[\.]?\d*',setstr)[0]
                #S LOGGIT!
                self.logger.info("Cell heater currently set to: "+set_temp+ " C")
                #S Return to sender.
                return "success " + set_temp + " C"
        
	def get_spec_pressure(self):
                response = str(self.gaugeController.send('#  RDCG2'))

                if '*' in response:
                        try:
                                pressure = float(response.split()[1])
                        except:
                                self.logger.exception("Unexpected response: " + response)
                                return 'fail'
                        return 'success ' + str(pressure)
                return 'fail'

        def get_pump_pressure(self):
                response = str(self.gaugeController.send('#  RDCG1'))
                
                if '*' in response:
                        try:
                                pressure = float(response.split()[1])
                        except:
                                self.logger.exception("Unexpected response: " + response)
                                return 'fail'
                        return 'success ' + str(pressure)
                return 'fail'

        def led_turn_on(self):
                self.time_tracker_on(self.flat_file)
                self.pdu.ledlamp.on()
                return 'success'

        def led_turn_off(self):
                self.pdu.ledlamp.off()
                self.time_tracker_off(self.flat_file)
                return 'success'
        
        #S Functions for tracking the time something has been on.
        #S Tested on my computer, so it should be fine. Definitely keep an eye
        #S on it though.
        
        def time_tracker_on(self,filename):
                #S Some extra path to put files in directory in log directory
                extra_path = self.base_directory+'/log/lamps//'
                #S Want to check if the lamp was already on, or if the
                #S the logger wasn't informed of a pwer off. In which case,
                #S we'll leave what ever the last start time was in there to
                #S be safe and continue from there.
                #S Here, it will try and open an existing log file for a lamp.
                try:
                        fd = open(extra_path+filename,'r')
                        lst = fd.readlines()
                        fd.close()
                        #S if it does open and the lamp appears to be on,
                        #S leave it on.
                        if len(lst[-1].split(',')) == 1:
                               return 'success'
                except:
                        pass
                        
                #S Otherwise, let's create a file, or just write the new time.
                #S Format for datetime objects being used.
                fmt = '%Y-%m-%dT%H:%M:%S'
                #S Get datetime string of current time.
                now = datetime.datetime.utcnow().strftime(fmt)
                #S Open file, append the current time, and close.
                #S Note: no EOL char, as it makes f.readlines shit.
                f = open(extra_path+filename,'a')
                f.write(now)
                f.close()
                return 'success'
                
        def time_tracker_off(self,filename):
                #S Paath
                extra_path = self.base_directory+'/log/lamps//'
                #S Format for datetime strings 
                fmt = '%Y-%m-%dT%H:%M:%S'
                #S Current time, datetime obj and string
                now = datetime.datetime.utcnow()
                nowstr = now.strftime(fmt)
                #S Open and read log. For some reason can't append and
                #S read at sametime.
                #S Try and open existing lamp log file.
                try:
                        f = open(extra_path+filename,'r')
                        lst = f.readlines()
                        f.close()
                        #S Check to see if there is a full line of entries at EOF, and if so,
                        #S skip the saving and update. this is because if there is a full
                        #S list of entries, this timeTrackOFF was envoked by the CtrlHandler.
                        #S The lamp was probably off already, but just in case we tell it again.
                        if len(lst[-1].split(',')) == 3:
                                return
                except:
                        lst = ['0,0,0','0,0,0']
                
                #S Otherwise, were going to do nothing. We'll keep lst in tries really.
                #S Get previous total time on. See the except for details on
                #S what should be happening. 
                try:

                        #S Get time and and put in seconds
                        prevtot = float(lst[-2].split(',')[-1])*3600.
                                                
                #S This is meant to catch the start of a new file, where
                #S there are no previoes times to add. It shouldn't catch
                #S if there are previuos times, but the end time and previous
                #S total were not recorded.
                #S I actually think it will now, as if it doesn't find a temptot,
                #S it will still throw with IndexError as it's supposed to for
                #S no prevtot instead. Do more investigating.
                except (IndexError):
                        prevtot = 0.
                        #print 'If you started a new lamp, ignore! Otherwise, something went wrong.'
                #S The last start time as datetime. As  a try it will catch if something is
                #S wrong with the log file. Should be at the TrackON, but this is most efficient?
                #S Just go check whats going on, maybe erase the bad line.
                #S THIS HAPPENS IF self.timeTrackOFF() was not run for the last sequence,
                #S that is if the end time of the last session was not recorded
                try:
                        start = datetime.datetime.strptime(lst[-1],fmt)
                except:
                        self.logger.error('ERROR: Start time was screwed, check '+filename)
                        return 'fail'
                #S Update total time on
                newtot_seconds = prevtot + (now-start).total_seconds()
                #S Make it a string of decimal hours
                totalstr = '%0.5f'%(newtot_seconds/3600.)       
                #S Actual file appending
                f = open(extra_path+filename,'a')
                f.write(','+nowstr+','+totalstr+'\n')
                f.close()
                return 'success'

        #S Function to open lamp log file and read how long the lamp has been on for.
        #S Used in checks to see if a lamp has been on for the required amount of time.
        #S Same basic structure as the off one. Returns SECONDS!!!
        #? Should we include an optio n to turn the lamp on if it is off??

        def time_tracker_check(self,filename):
                #S Paath
                extra_path = self.base_directory+'/log/lamps//'
                #S Format for datetime strings 
                fmt = '%Y-%m-%dT%H:%M:%S'
                #S Current time
                now = datetime.datetime.utcnow()                
                #S Open and read log. For some reason can't append and
                #S read at sametime.
                #TODO Find way to read file from bottom up, only need
                #TODO last two lines.
                try:
                        f = open(extra_path+filename,'r')
                        lst = f.readlines()
                        f.close()
                except:
                        lst = '0,0,0'
                #S Check to see if there is a full line of entries at EOF, and if so,
                #S skip the saving and update. this is because if there is a full
                #S list of entries, this timeTrackOFF was envoked by the CtrlHandler.
                #S The lamp was probably off already, but just in case we tell it again.
                if len(lst[-1].split(',')) == 3:
                        print 'The lamp is off right now, do we want it on?'
                #S Get the datetime string from the last line, which should be the only
                #S entry in that line. 
                try:
                        start = datetime.datetime.strptime(lst[-1],fmt)
                except:
                        self.logger.error('ERROR: Start time was screwed, check '+filename)
                #S Calculate the time that the lamp has been on so far. SECONDSS!!
                onTime = (now - start).total_seconds()
                return 'success ' + str(onTime)

        """
        ###
        # DYNAPOWER STATUS QUERY for spectrograph.py
        ###

        #S These are commands to return the updated status of the dynapowers
        #S to spectrogrsph for writing heades. The dynapower.updtaeStatus
        #S returns a dictionary which we convert to a string with json.dumps()
        #S and concatenate that onto 'success '. See how this response is handled
        #S in spectrograph.py.
        def update_dynapower1(self):
                status_dict = self.dynapower1.updateStatus()
                dict_str = json.dumps(status_dict)
                return 'success '+dict_str

        def update_dynapower2(self):
                status_dict = self.dynapower2.updateStatus()
                dict_str = json.dumps(status_dict)
                return 'success '+dict_str
        """        
                



        ###
        # EXPOSURE METER FUNCTIONS
        ###

        #S Restart the exposure meter if it were paused for backlighting the fiber.
        #S This only works if the exposure meter is in the loop in logexpmeter.
	def start_log_expmeter(self):
		try:
                        self.logger.info('Starting to log expmeter measurements')
                        self.pause_for_backlight = False
			return 'success'
		except:
			return 'fail'

        #S Stop the exposure meter, inteded for use only in the backlighting portion of
        #S logexpmeter main loop. This 'waits' for the high voltage to be turned off. This is
        #S a sort of weird way to do it, but it saves the time for waiting on more comm while
        #S confirming it is off. 
	def stop_log_expmeter(self):
		try:
                        self.pause_for_backlight = True
                        #time.sleep(10)
                        while self.exp_highvoltage:
                                time.sleep(0.1)
			return 'success'
		except:
			return 'fail'

        #TODO I think we need to add some more functions in case
        #TODO we need to reset attributes of the exposure meter,
        #TODO e.g. if we want to change the Period.
        
        #S Power on the exposure meter and make continuous
        #S readings that are logged. A maxsafecount variable is
        #S defined here that will act as a catch if there
        #S is an overexposure hopefully before any damage is done.         
        def logexpmeter(self):
                #S Turn expmeter on
                self.pdu.expmeter.on()
                self.pause_for_backlight = False
                self.expmeter_total = 0.
                
                #S The maximum count threshold we are currently allowing.
                #S Used as trigger level for shutdown.
                #TODO Get a real number for this.
                MAXSAFECOUNT = 30000000#500000.0

                #S Number of measurements we want to read per second.
                MEASUREMENTSPERSEC = 1.0
                #S Give some time for command to be sent and the outlet to
                #S power on. Empirical wait time from counting how long it
                #S it took to turn on. Potentially shortened?
                time.sleep(1)
                #S Sends comand to set Period of expmeter measurements.
                #S See documentation for explanation.
                self.expmeter_com.send('P' + chr(int(100.0/MEASUREMENTSPERSEC)))
                #S Turns on the high voltage.
                self.logger.info('Exposure meter high voltage on')
                self.exp_highvoltage = True
                self.expmeter_com.send('V'+chr(1)+chr(1))
                #S Sets the trigger for the shutter.
                self.logger.info('Exposure meter shutter trigger set')
                self.expmeter_com.send('O' + chr(1))
                #S Begin continuous measurements.
                self.logger.info('starting continuous exposure meter measurements')
                self.expmeter_com.send('C')
                #S Open up connection for reading, remains open.
                self.expmeter_com.ser.open()
                #S Loop for catching exposures.
                while self.expmeter_com.ser.isOpen() and self.log_exposure_meter:
                        if self.pause_for_backlight:
                                self.expmeter_com.ser.close()
                                # Shut the shutter
                                self.expmeter_com.send('O' + chr(0))
                                self.logger.info('Closed expmeter shutter')
                                #S High voltage off.
                                self.expmeter_com.send('V'+ chr(0) + chr(0) + self.expmeter_com.termstr) # turn off voltage
                                self.logger.info('turned off exposure meter high voltage')
                                self.exp_highvoltage = False
                                #S Stop measurements
                                self.expmeter_com.send("\r")
                                self.logger.info('stopped expmeter measurements')
                                self.pdu.expmeter.off()
                                #time.sleep(5)
                                #S waiting for self.start_log_expmeter
                                while self.pause_for_backlight:
                                        time.sleep(0.1)
                                self.pdu.expmeter.on()
                                time.sleep(1)
                                #S Sends comand to set Period of expmeter measurements.
                                #S See documentation for explanation.
                                self.expmeter_com.send('P' + chr(int(100.0/MEASUREMENTSPERSEC)))
                                #S Turns on the high voltage.
                                self.logger.info('Exposure meter high voltage on')
                                self.expmeter_com.send('V'+chr(1)+chr(1))
                                self.exp_highvoltage = True
                                #S Sets the trigger for the shutter.
                                self.logger.info('Exposure meter shutter trigger set')
                                self.expmeter_com.send('O' + chr(1))
                                #S Begin continuous measurements.
                                self.logger.info('starting continuous exposure meter measurements')
                                self.expmeter_com.send('C')
                                #S Open up connection for reading, remains open.
                                self.expmeter_com.ser.open()
        
                        try:
                                #ipdb.set_trace()
                                #S While the register is empty, wait
                                #TODO Add time out, throw exception
                                while self.expmeter_com.ser.inWaiting() < 4:
                                        time.sleep(0.01)
                                #S Once there is a reading, get it.
                                rawread = self.expmeter_com.ser.read(4)
                                #S Unpack the reading from the four-byte struct.
                                reading = struct.unpack('>I',rawread)[0]
                        
                                #S Testing maxsafecount condition
                                ## reading = 100001.0

                        #S The exception if something goes bad, negative reading is the key.   
                        except:
                                time.sleep(.5)
                                self.expmeter_com.logger.exception('Expmeter connectino unexpectedly closed.')
                                reading = -999                            
                        
                        #S This is the check against the maxsafecount.    
                        #S Tested to see if caught, passed.Utlimately just
                        #S turned off expmeter, program still running. May need
                        #S to implement other actions?
                        if reading > MAXSAFECOUNT:
                                self.expmeter_com.logger.error("The exposure meter reading is: " + datetime.datetime.strftime(datetime.datetime.utcnow(),'%Y-%m-%d %H:%M:%S.%f') + " " + str(reading)+" > maxsafecount="+str(MAXSAFECOUNT))
                                mail.send("Exposure meter has shut down",
                                          "Dear Benevolent Humans,\n\n"+
                                          "My exposure meter was saturated and I shut it down to protect it. "+
                                          "Can you please investigate and, if safe, restart the spectrograph server? "+
                                          "No exposure meter data will be recorded until you do.\n\n"+
                                          "Love,\nMINERVA",level="serious")
                                break
                        #? Not sure if we need this guy, seems like we are already logging?
                        path = self.base_directory + "/log/" + self.night() + "/"
                        if not os.path.exists(path): os.mkdir(path)

                        #S add the reading to the running total
                        self.expmeter_total += reading
                        
                        with open(path + "expmeter.dat", "a") as fh:
                                fh.write(datetime.datetime.strftime(datetime.datetime.utcnow(),'%Y-%m-%d %H:%M:%S.%f') + "," + str(reading) + "\n")
                        self.expmeter_com.logger.info("The exposure meter reading is: " + str(reading))

                #S Close the comm port
                self.expmeter_com.close() # close connection
                
                #S If the loop is broken, these are shutdown procedures.
		# Shut the shutter
                self.expmeter_com.send('O' + chr(0))
                self.logger.info('Closed expmeter shutter')
                #S Stop measurements
                self.expmeter_com.send("\r")
                self.logger.info('stopped expmeter measurements')
                #S High voltage off.
                self.expmeter_com.send('V'+ chr(0) + chr(0) + self.expmeter_com.termstr) # turn off voltage
                self.logger.info('turned off exposure meter high voltage')
                #S Turn off power to exposure meter
                self.pdu.expmeter.off()

        #S functions for locally tracking the expmeter total
                
        def get_expmeter_total(self):
                #S put this in a try in case we aren't logging the exposure meter
                #S because we initialize the self.expmeter_total in 
                try:
                        total = self.expmeter_total
                        return 'success ' + str(total)
                except:
                        self.logger.error('No expmeter_total being tracked')
                        return 'fail'

        def reset_expmeter_total(self):
                try:
                        self.expmeter_total = 0
                        return 'success'
                except:
                        self.logger.exception('Failed to reset the expmeter total')
                        return 'fail'
                                
                

        #S going to log the pressures of the chamber and the pump
        def log_pressures(self):
		
                while True:
                        path = self.base_directory + "/log/" + self.night() + "/"
                        if not os.path.exists(path): os.mkdir(path)
                        
			# get the pressure in the spectrograph
                        with open(path + 'spec_pressure.log','a') as fh:
                                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
                                response = self.get_spec_pressure()
                                if response <> 'fail':
                                        specpres = float(response.split()[1])
                                        fh.write('%s,%s\n'%(now,specpres))
					self.nfailspec = 0 
				else:
					specpres = 'UNKNOWN'
					self.nfailspec += 1

			# get the pressure in the lines before the spectrograph
                        with open(path + 'pump_pressure.log','a') as fh:
                                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
                                response = self.get_pump_pressure()
                                if response <> 'fail':
                                        pumppres = float(response.split()[1])
                                        fh.write('%s,%s\n'%(now,pumppres))
					self.nfailpump = 0 
				else: 
					pumppres = 'UNKNOWN'
					self.nfailpump += 1

			# get the status of each port
        		try:
                                ventvalveopen = self.benchpdu.ventvalve.status()
        			if ventvalveopen: ventvalvetxt = "open"
                		else: ventvalvetxt = "closed"
                        except:
                                ventvalveopen = "unknown"
        			ventvalvetxt = "unknown"
                		
                        try:
        			pumpvalveopen = self.benchpdu.pumpvalve.status()
                		if pumpvalveopen: pumpvalvetxt = "open"
                        	else: pumpvalvetxt = "closed"
                        except:
                                pumpvalveopen = "unknown"
        			pumpvalvetxt = "unknown"

                        try:        
                                pumpon = self.controlroompdu.pump.status()
                		if pumpon: pumptxt = 'on'
        			else: pumptxt = 'off'
                        except:
                                pumpon = "unknown"
                                pumptxt = 'unknown'

                        try:
        			compressoron = self.controlroompdu.compressor.status()
                		if compressoron: compressortxt = 'on'
                        	else: compressortxt = 'off'
                        except:
                                compressoron = "unknown"
                                compressortxt = "unknown"

			# Catch potential failure modes
			# spectrograph pressure gauge failed
			if specpres == 'UNKNOWN':
				self.logger.error('The spectograph gauge has failed to read ' + str(self.nfailspec) + ' consecutive times')
				if self.nfailspec > 3 and (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
					mail.send("Spectrograph pressure gauge failed?",
						  "Dear Benevolent Humans,\n\n"+
						  "The spectrograph pressure gauge has failed to return a value 3\n"+
						  "consecutive times. Please investigate.\n\n"
						  "Love,\nMINERVA",level="serious")
					self.lastemailed = datetime.datetime.utcnow()
			elif not compressoron:
				self.logger.error('The air compressor is off.')
				if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
					mail.send("Air compressor failed?",
						  "Dear Benevolent Humans,\n\n"+
						  "The air compressor is off. It is required to control the vacuum valves " + 
						  "and stabilize the optical bench. Please investigate immediately.\n\n"+
						  "Love,\nMINERVA",level="serious")
					self.lastemailed = datetime.datetime.utcnow()
			elif specpres > 0.006:
				self.logger.error("the spectrograph pressure is out of range")
				self.logger.info("The pump pressure is " + str(pumppres) + " mbar")
                                self.logger.info("The spectrograph pressure is " + str(specpres) + " mbar")
				self.logger.info("The compressor is " + compressortxt)
				self.logger.info("The vacuum pump is " + pumptxt)
				self.logger.info("The vent valve is " + ventvalvetxt)
				self.logger.info("The pump valve is " + pumpvalvetxt)

				if pumppres != 'UNKNOWN' and pumppres < specpres and pumpon and (not ventvalveopen) and pumpvalveopen:
					# 0) pumping down after venting
					# diagnosis:
					#    spec pressure > 0.006
					#    pump pressure < spec pressure
					# action:
					# email in case of misdiagnosis
					if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
						mail.send("Spectrograph pressure out of range!",
							  "Dear Benevolent Humans,\n\n"+
							  "The spectrograph pressure (" + str(specpres) + " mbar) is out of range. " +
							  "I believe I am just pumping down after being vented and no action is required. "+
							  "If that is not the case, this should be investigated immediately.\n\n"
							  "The pump pressure is " + str(pumppres) + " mbar\n"+
							  "The spectrograph pressure is " + str(specpres) + " mbar\n"+
							  "The compressor is " + compressortxt + '\n'+
							  "The vacuum pump is " + pumptxt + '\n'+
							  "The vent valve is " + ventvalvetxt + '\n'+
							  "The pump valve is " + pumpvalvetxt + '\n\n'+
							  "Love,\nMINERVA",level="serious")
						self.lastemailed = datetime.datetime.utcnow()
				elif pumppres != 'UNKNOWN' and pumppres < 0.006 and pumpon and (not ventvalveopen) and pumpvalveopen:
					# 1) a power outage closed the pump valve and the leak rate 
					# caused it to slowly come back up slowly (bad, but not terrible)
					# diagnosis:
					#    spec pressure > 3
					#    pump pressure < 3
					#    pump on
					#    vent valve closed (off)
					#    pump valve open (on)
					# action:
					# email only asking user to open the pump valve after confirmation of situation (serious)
					# too risky to automate
					if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
						mail.send("Spectrograph pressure out of range!",
							  "Dear Benevolent Humans,\n\n"+
							  "The spectrograph pressure (" + str(specpres) + " mbar) is out of range. " +
							  "While this could be a catastrophic and unplanned venting that could " + 
							  "damage the spectrograph and should be investigated immediately, this " +
							  "is usually caused by a power outage that closed the pump valve.\n\n."
							  "The pump pressure is " + str(pumppres) + " mbar\n"+
							  "The spectrograph pressure is " + str(specpres) + " mbar\n"+
							  "The compressor is " + compressortxt + '\n'+
							  "The vacuum pump is " + pumptxt + '\n'+
							  "The vent valve is " + ventvalvetxt + '\n'+
							  "The pump valve is " + pumpvalvetxt + '\n\n'+
							  "Please\n\n" +
							  "1) log on to 192.168.1.40\n"	
							  "2) Confirm the pump is on\n"+
							  "3) log on to 192.168.1.40\n"
							  "4) Check to make sure the vent valve is closed (off)\n"+
							  "5) Open the pump valve by turning it on.\n\n" +
							  "The spectrograph pressure is currently unstable and our RV precision will suffer until this is addressed.\n\n"
							  "Love,\nMINERVA",level="serious")
						self.lastemailed = datetime.datetime.utcnow()
				elif (pumppres != 'UNKOWN') and (pumppres > 3) and pumpvalveopen:
					# 2) the pump failed and it's venting through the pump (very bad)
					#    spec pressure > 3
					#    pump pressure > 3
					#    pump valve open (on)
					#    pump on (probably, but not necessarily)
					#    vent valve closed (probably, but not necessarily)
					# action:
					# Close pump valve immediately
					# Turn off pump?
					# Email asking user to investigate (critical)
					try: self.benchpdu.pumpvalve.off()
                                        except: pass
					if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
						mail.send("Spectrograph vacuum failure!!!",
							  "Dear Benevolent Humans,\n\n"+
							  "The spectrograph pressure (" + str(specpres) + " mbar) is out of range " +
							  "and the pump valve is open. This probably means THE PUMP HAS FAILED " + 
							  "CATASTROPHICALLY AND DAMAGE TO THE SPECTOGRAPH COULD OCCUR! " + 
							  "I have closed the pump valve, but this should be investigated in " + 
							  "person and remotely as soon as possible.\n\n"
							  "The pump pressure is " + str(pumppres) + " mbar\n"+
							  "The spectrograph pressure is " + str(specpres) + " mbar\n"+
							  "The compressor is " + compressortxt + '\n'+
							  "The vacuum pump is " + pumptxt + '\n'+
							  "The vent valve is " + ventvalvetxt + '\n'+
							  "The pump valve is " + pumpvalvetxt + '\n\n'+
							  "Love,\nMINERVA",level="critical")
						self.lastemailed = datetime.datetime.utcnow()
				elif pumppres != 'UNKNOWN' and pumppres > 0.006 and (not pumpvalveopen) and ventvalveopen and (not pumpon):
					# 3) we intentionally vented the spectrograph (probably fine as this is intentional)
					#    spec pressure > 3
					#    pump pressure > 3
					#    pump off
					#    vent valve open
					#    pump valve closed
					# action:
					# Email just in case venting was not intentional (serious)
					if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
						mail.send("Spectrograph intentionally venting?",
							  "Dear Benevolent Humans,\n\n"+
							  "The spectrograph pressure (" + str(specpres) + " mbar) is out of range, " +
							  "but the vent valve is open, the pump is off, and the pump valve is closed, "+
							  "which means the spectrograph is likely being vented intentionally. "+
							  "If that is not the case, immediate investigation is required.\n\n"
							  "The pump pressure is " + str(pumppres) + " mbar\n"+
							  "The spectrograph pressure is " + str(specpres) + " mbar\n"+
							  "The compressor is " + compressortxt + '\n'+
							  "The vacuum pump is " + pumptxt + '\n'+
							  "The vent valve is " + ventvalvetxt + '\n'+
							  "The pump valve is " + pumpvalvetxt + '\n\n'+
							  "Love,\nMINERVA",level="serious")
						self.lastemailed = datetime.datetime.utcnow()
				else:
					# 4) unknown failure (gauge failure?)
					#    spec pressure > 3
					#    any other configuration
					# action:
					# close pump valve
					# close vent valve
					# turn off pump?
					# email asking user to investigate (critical)
					#self.benchpdu.pumpvalve.off()
					#self.benchpdu.ventvalve.off()
					if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:				
						mail.send("Spectrograph pressure in unknown state!!!",
							  "Dear Benevolent Humans,\n\n"+
							  "The spectrograph pressure (" + str(specpres) + " mbar) is out of range, " +
							  "and I'm not sure what's going on. It could be a catastrophic problem. "+
							  "You need to investigate immediately. SERIOUS DAMAGE IS POSSIBLE.\n\n"
							  "The pump pressure is " + str(pumppres) + " mbar\n"+
							  "The spectrograph pressure is " + str(specpres) + " mbar\n"+
							  "The compressor is " + compressortxt + '\n'+
							  "The vacuum pump is " + pumptxt + '\n'+
							  "The vent valve is " + ventvalvetxt + '\n'+
							  "The pump valve is " + pumpvalvetxt + '\n\n'+
							  "Love,\nMINERVA",level="critical")
						self.lastemailed = datetime.datetime.utcnow()

                        time.sleep(0.5)
                     
        #S Used in the Console CTRL Handler, where we 
        #S can put all routines to be perfomred in here I think. It
        #S may also catch accidental shutdown, not sure about loss of
        #S power. INCLUDES:
        #S Function to ensure power is shut off to exposure meter
        def safe_close(self,signal):
		self.log_exposure_meter = False
                self.led_turn_off()
		self.i2stage_disconnect()
                try: self.gaugeController.close()
                except: pass
                while self.expmeter_com.ser.isOpen():
                        time.sleep(0.1)
                self.backlight_off() # don't leave the backlight on!
		
		#S Something fucky going on here, won't let me close browsers.
		#TODO
#		self.dynapower1.browser.close()
#		self.dynapower2.browser.close()

                
                
if __name__ == '__main__':

	base_directory = 'C:\\minerva-control'
	test_server = server('spectrograph_server.ini',base_directory)

        # make sure it didn't die with the backlight on
        test_server.logger.info('turning backlight off')
        test_server.backlight_off()
        test_server.logger.info('backlight off')
#        status = test_server.chiller_status_dict()
        
#        test_server.kill_si_image()
#        thisnight = 'n20991332'
#        path = test_server.base_directory + '/log/' + thisnight
#        test_server.update_logpaths(path)
#	win32api.SetConsoleCtrlHandler(test_server.safe_close,True)

        logpath_thread = threading.Thread(target=test_server.logpath_watch)
        logpath_thread.name = 'Kiwispec'
        logpath_thread.start()

        pressure_thread = threading.Thread(target=test_server.log_pressures)
	pressure_thread.name = 'Kiwispec'
        pressure_thread.start()

#        expmeter_thread = threading.Thread(target=test_server.logexpmeter)
#        expmeter_thread.name = 'Kiwispec'
#        expmeter_thread.start()
	test_server.logger.warning('*** EXPMETER disabled ***')

        # log the chiller temps
#        chiller_thread = threading.Thread(target=test_server.logchiller)
#        chiller_thread.name = 'Kiwispec'
#        chiller_thread.start()
	test_server.logger.warning('*** chiller disabled ***')
	
	#	test_server.logexpmeter()
#	ipdb.set_trace()
#	test_server.move_i2(position='science')
#        test_server.cell_heater_get_set_temp()
#        ipdb.set_trace()
	serverThread = threading.Thread(target = test_server.run_server())
	serverThread.name = 'Kiwispec'
#	ipbd.set_trace()
        serverThread.start()
	
	

	
	
	
	
	
