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
import dynapower
from PyAPT import APTMotor
import win32api
import atexit
import re

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

		# reset the night at 10 am local
		#S today gets current time in utc
		today = datetime.datetime.utcnow()
		#S Checks if the hour is between 10 and 16 (local time in Arizona?)
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        #? If true, add a day? But why? 
                        today = today + datetime.timedelta(days=1)
                #S Just file name string.
		self.night = 'n' + today.strftime('%Y%m%d')
                #S Defined later.
                self.setup_logger()
                #S Defined later.
                self.set_data_path()
#                self.file_name = ''
                #S Create all class objects
                self.create_class_objects()

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
                        self.header_buffer = ''
		except:
			print('ERROR accessing ', self.name, ".", 
				   self.name, " was not found in the configuration file", configfile)
			return 
		
	#create logger object and link to log file
	def setup_logger(self):
                #S Looks for existing log path, and creates one if none exist.
		log_path = self.base_directory + '/log/' + self.night
		
                if os.path.exists(log_path) == False:
                        os.mkdir(log_path)
                #S the log's format for entries.
                fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
                #S The log's date format for entries.
                datefmt = "%Y-%m-%dT%H:%M:%S"
                #S Gets logger name form config file entry. 
                self.logger = logging.getLogger(self.logger_name)
                #S From later on, setting level to DEBUG just
                #S ignores debug meesages that occur, those from
                #S ipdb?
                self.logger.setLevel(logging.DEBUG)
                #S Makes log entries conform to those formats above.
                formatter = logging.Formatter(fmt,datefmt=datefmt)
                #S Not sure how this converter works, but just takes GMT to
                #S local I bleieve.
                formatter.converter = time.gmtime

                #clear handlers before setting new ones                                                                               
                self.logger.handlers = []

                fileHandler = logging.FileHandler(log_path + '/' + self.logger_name + '.log', mode='a')
                fileHandler.setFormatter(formatter)
                self.logger.addHandler(fileHandler)

                # add a separate logger for the terminal (don't display debug-level messages)                                         
                console = logging.StreamHandler()
                console.setFormatter(formatter)
                #? What is INFO level?
                console.setLevel(logging.INFO)
                #? Purpossely redone?
                self.logger.setLevel(logging.DEBUG)
                self.logger.addHandler(console)

		'''
		self.logger = logging.getLogger(self.name)
		formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
		fileHandler = logging.FileHandler(self.base_directory + '/log/' + folder + '/telecom_server.log', mode='a')
		fileHandler.setFormatter(formatter)
		streamHandler = logging.StreamHandler()
		streamHandler.setFormatter(formatter)

		self.logger.setLevel(logging.DEBUG)
		self.logger.addHandler(fileHandler)
		self.logger.addHandler(streamHandler)
		'''
        #S Finds path for data, creates if none exist. What is the point of the
	#S night arguement though? Doesn;t go into self., as that's defined
	#S earlier. 
	def set_data_path(self,night='dump'):
		self.data_path = self.data_path_base + '\\' + self.night
		if not os.path.exists(self.data_path):
			os.makedirs(self.data_path)
		return 'success'

	#S Create class objects
	def create_class_objects(self):
                self.expmeter_com = com.com('expmeter',self.night,configfile=self.base_directory + '/config/com.ini')
                self.cellheater_com = com.com('I2Heater',self.night,configfile=self.base_directory + '/config/com.ini')
                self.dynapower1 = dynapower.dynapower(self.night,base=self.base_directory,configfile='dynapower_1.ini',browser=True)
                self.dynapower2 = dynapower.dynapower(self.night,base=self.base_directory,configfile='dynapower_2.ini',browser=True)

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
                elif tokens[0] == 'get_vacuum_pressure':
                        response = self.get_vacuum_pressure()
                elif tokens[0] == 'get_atm_pressure':
                        response = self.get_atm_pressure()
		elif tokens[0] == 'get_filter_name':
			response = self.get_filter_name(tokens[1])
		elif tokens[0] == 'expose':
			response = self.expose(tokens[1])
		elif tokens[0] == 'set_camera_param':
			response = self.set_camera_param(tokens[1])
		elif tokens[0] == 'set_data_path':
			response = self.set_data_path(tokens[1])
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
		elif tokens[0] == 'i2stage_move':
			response = self.i2stage_move(tokens[1])
		elif tokens[0] == 'thar_turn_on':
			response = self.thar_turn_on()
		elif tokens[0] == 'thar_turn_off':
			response = self.thar_turn_off()
		elif tokens[0] == 'white_turn_on':
			response = self.white_turn_on()
		elif tokens[0] == 'white_turn_off':
			response = self.white_turn_off()
		
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
          

        def set_file_name(self,param):
                if len(param.split()) != 1:
			self.logger.error('parameter mismatch')
			return 'fail'
		self.logger.info('setting name to:' + param)
		self.file_name = self.data_path + '\\' + param                
                return 'success'
		
	def save_image(self):


		self.logger.info('saving image to:' + self.file_name)

                try:
                        shutil.move("C:/IMAGES/I",self.file_name)
                        return 'success'
		except: return 'fail'

        def get_index(self,param):
                files = glob.glob(self.data_path + "/*.fits*")
                return 'success ' + str(len(files)+1)
		
	def write_header(self,param):		
		self.header_buffer = self.header_buffer + param
		return 'success'
		
	def write_header_done(self,param):

		try: 
			self.logger.info("Writing header for " + self.file_name)
		except: 
			self.logger.error("self.file_name not defined; saving failed earlier")
			self.logger.exception("self.file_name not defined; saving failed earlier")
			return 'fail'

		try:
			header_info = self.header_buffer + param
			self.header_buffer = ''
			f = pyfits.open(self.file_name, mode='update')
			for key,value in json.loads(header_info,object_pairs_hook=collections.OrderedDict).iteritems():
				if isinstance(value, (str, unicode)):
					f[0].header[key] = value
				else:
					f[0].header[key] = (value[0],value[1])

                        f[0].header['SIMPLE'] = True
                        f[0].header['EXPTIME'] = float(f[0].header['PARAM24'])/1000.0
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

                        # recast as 16 bit unsigned integer (2x smaller with no loss of information)
                        #data = f[0].data.astype('uint16')
                        #f.close()

                        # Write final image
                        #pyfits.writeto(filename,data,hdr)
                        
			f.flush()
			f.close()
		except:
			self.logger.error("failed to create header")
			self.logger.exception("failed to create header")
			return 'fail'
		return 'success'

        ###
        # THORLABS STAGE, For Iodine Lamp
        ###

        #TODO Is it too much to be logging at each connect/disconnect? I think
        #TODO so, so I commented them out but did leave in error logs. There is also opportunity to
        #TODO make moveI2Stage check against current position and bypass command if so.
        #TODO I think this is negligible in the time it would take to not move, and sending the
        #TODO command should be quick anyway. Might as well I'm thinking.
        
        #S Initialize the stage, needs to happen before anyhting else.
        def i2stage_connect(self):
                #S Unique serial number for I2 stage, hardwaretype for BSC201(?)
                #S Using HW=12, waiting for response form THORLABS. Seems to work fine
                #S in testing though.
                SN = 40853360
                HWTYPE = 12
                
                
                
                #S Try and connect and initialize
                try:
                        #S Connect the motor with credentials above.
                        self.motorI2 = APTMotor(SN , HWTYPE)
                        #S Initialize motor, we can move and get info with this.
                        #S Can't be controllecd by anything else until relesased.
                        self.motorI2.initializeHardwareDevice()
                        #S Get curtrent position, needed for logging?
                        ## currentPos = self.motorI2.getPos()
                        #S Write it down, commented out for now.
                        ## self.logger.info("Iodine stage connected and initialized. Started at position: %0.5f mm"%(currentPos))

                        #S Location str fot header, unknown because just started.
                        self.motorI2.lastlocationstr = 'unknown'
                        
                #S Something goes wrong. Remember, only one application can connect at
                #S a time, e.g. Kiwispec but not *.py
                except:
                        self.logger.error("ERROR: did not connect to the Iodine stage.")
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

        #S Get the position of the I2 stage

        def i2stage_get_pos(self):
                try:
                        #S Query position
                        current_pos = self.motorI2.getPos()
                        return 'sucess' + current_pos
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
                        self.motorI2.mAbs(self.i2positions[locationstr.lower()])
                except:
                        #throw and log error on bad position
                        self.logger.error("ERROR: Iodine failed to move or invalid location.")

                #S need to log position, stuff, andything else?
                new_pos = self.motorI2.getPos()
                self.logger.info("Iodine stage moved from %0.5f mm to %0.5f mm"%(prev_pos,new_pos))
                return 'success'



        ###
	# CELL HEATER FUNCTIONS/COMMANDS
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
                #S If iy was off, we'll turn it on. Checked status due to toggle nature of heater power.
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
        
	def get_vacuum_pressure(self):
                specgauge = com.com('specgauge',self.night,configfile=self.base_directory + '/config/com.ini')
                response = str(specgauge.send('RD'))
                #ipdb.set_trace()
                if response == '': return 'fail'
                return 'success ' + response

        def get_atm_pressure(self):
                atmgauge = com.com('atmGauge',self.night,configfile=self.base_directory + '/config/com.ini')
                atmgauge.send('OPEN')
                pressure = atmgauge.send('R')
                atmgauge.send('CLOSE')
                ipdb.set_trace()
                return 'success ' + str(pressure)

	###
	# LAMPS
	###

         #TODODYNA need to incorporate outlet names, etc.        
        #S Functions for toggling the ThAr lamp
        def thar_turn_on(self):
                self.dynapower1.on('tharLamp')
                self.time_tracker_on(self.thar_file)
                
                return
        def thar_turn_off(self):
                self.dynapower1.off('tharLamp')
                self.time_tracker_off(self.thar_file)
                return
        #S Functions for toggling the White lamp
        def white_turn_on(self):
                self.time_tracker_on(self.white_file)
                self.dynapower1.on('whiteLamp')
                return
        def white_turn_off(self):
                self.dynapower1.off('whiteLamp')
                self.time_tracker_off(self.white_file)
                return

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
                fd = open(extra_path+filename,'r')
                lst = fd.readlines()
                fd.close()
                if len(lst[-1].split(',')) == 1 :
                       return
                #S Format for datetime objects being used.
                fmt = '%Y-%m-%dT%H:%M:%S'
                #S Get datetime string of current time.
                now = datetime.datetime.utcnow().strftime(fmt)
                #S Open file, append the current time, and close.
                #S Note: no EOL char, as it makes f.readlines shit.
                f = open(extra_path+filename,'a')
                f.write(now)
                f.close()
                return
                
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
                #TODO Find way to read file from bottom up, only need
                #TODO last two lines.
                f = open(extra_path+filename,'r')
                lst = f.readlines()
                f.close()
                #S Check to see if there is a full line of entries at EOF, and if so,
                #S skip the saving and update. this is because if there is a full
                #S list of entries, this timeTrackOFF was envoked by the CtrlHandler.
                #S The lamp was probably off already, but just in case we tell it again.
                if len(lst[-1].split(',')) == 3:
                        return
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
                #S Update total time on
                newtot_seconds = prevtot + (now-start).total_seconds()
                #S Make it a string of decimal hours
                totalstr = '%0.5f'%(newtot_seconds/3600.)       
                #S Actual file appending
                f = open(extra_path+filename,'a')
                f.write(','+nowstr+','+totalstr+'\n')
                f.close()
                return

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
                f = open(extra_path+filename,'r')
                lst = f.readlines()
                f.close()
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
                return onTime
                



        ###
        # EXPOSURE METER FUNCTIONS
        ###

        #TODO I think we need to add some more functions in case
        #TODO we need to reset attributes of the exposure meter,
        #TODO e.g. if we want to change the Period.
        
        #S Power on the exposure meter and make continuous
        #S readings that are logged. A maxsafecount variable is
        #S defined here that will act as a catch if there
        #S is an overexposure hopefully before any damage is done.         
        def logexpmeter(self):
                #S The maximum count threshold we are currently allowing.
                #S Used as trigger level for shutdown.
                #TODO Get a real number for this.
                MAXSAFECOUNT = 150000.0
                #S Number of measurements we want to read per second.
                MEASUREMENTSPERSEC = 1.0
                #S Create dynapower class, used only in this function. Note no browser should be opened.
                expdynapower = dynapower.dynapower(self.night,base=self.base_directory,configfile='dynapower_1.ini')
                #S Turn it on.
                expdynapower.on('expmeter')
                #S Give some time for command to be sent and the outlet to
                #S power on. Empirical wait time from counting how long it
                #S it took to turn on. Potentially shortened?
                time.sleep(2)
                #S Sends comand to set Period of expmeter measurements.
                #S See documentation for explanation.
                self.expmeter_com.send('P' + chr(int(100.0/MEASUREMENTSPERSEC)))
                #S Turns on the high voltage.
                self.expmeter_com.send('V'+chr(1)+chr(1))
                #S Sets the trigger for the shutter.
                self.expmeter_com.send('O' + chr(1))
                #S This command is supposed to allow continuous measurements,
                #S but no difference if it is made or not.
                ##expmeter.send('L')
                #S Begin continuous measurements.
                self.expmeter_com.send('C')
                #S Open up connection for reading, remains open.
                self.expmeter_com.ser.open()
                #S Loop for catching exposures.
                while self.expmeter_com.ser.isOpen():
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
                                self.expmeter_com.logger.exception('-999')
                                reading = -999
                                print 'WE HIT THE SPEC_SERV EXCEPTION!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
                                #TODO Run this solution by Jason
                                if not self.expmeter_com.ser.isOpen():
                                        self.expmeter_com.open()
                                
                        
                        #S This is the check against the maxsafecount.    
                        #S Tested to see if caught, passed.Utlimately just
                        #S turned off expmeter, program still running. May need
                        #S to implement other actions?
                        if reading > MAXSAFECOUNT:
                                self.expmeter_com.logger.error("The exposure meter reading is: " + datetime.datetime.strftime(datetime.datetime.utcnow(),'%Y-%m-%d %H:%M:%S.%f') + " " + str(reading)+" > maxsafecount="+str(MAXSAFECOUNT))                    
                                break
                        #? Not sure if we need this guy, seems like we are already lgging?
                        with open(self.base_directory + "/log/" + self.night + "/expmeter.dat", "a") as fh:
                                fh.write(datetime.datetime.strftime(datetime.datetime.utcnow(),'%Y-%m-%d %H:%M:%S.%f') + "," + str(reading) + "\n")
                        self.expmeter_com.logger.info("The exposure meter reading is: " + datetime.datetime.strftime(datetime.datetime.utcnow(),'%Y-%m-%d %H:%M:%S.%f') + " " + str(reading))
                        
                #S If the loop is broken, these are shutdown procedures.
                #S Stop measurements
                self.expmeter_com.send("\r")
                #S High voltage off.
                self.expmeter_com.send('V'+ chr(0) + chr(0) + self.expmeter_com.termstr) # turn off voltage
                #S Close the comm port
                self.expmeter_com.close() # close connection
                #S Turn of power to exposure meter
                expdynapower.off('expmeter')
                
        #S Used in the Console CTRL Handler, where we 
        #S can put all routines to be perfomred in here I think. It
        #S may also catch accidental shutdown, not sure about loss of
        #S power. INCLUDES:
        #S Functino to ensure power is shut off to exposure meter
        def safe_close(self,signal):
                dynapower1 = dynapower.dynapower(self.night,base=self.base_directory,configfile='dynapower_1.ini')
                dynapower1.off('expmeter')
		self.thar_turn_off()
		self.white_turn_off()
		self.i2stage_disconnect()

                
                
if __name__ == '__main__':

	base_directory = 'C:\minerva-control'

	test_server = server('spectrograph.ini',base_directory)
#	win32api.SetConsoleCtrlHandler(test_server.safe_close,True)



#        print test_server.get_atm_pressure()
	
#        print test_server.get_vacuum_pressure()
#        ipdb.set_trace()
	
	thread = threading.Thread(target=test_server.logexpmeter)
	thread.start()
	
	#	test_server.logexpmeter()
#	ipdb.set_trace()
#	test_server.move_i2(position='science')
#        test_server.cell_heater_get_set_temp()
#        ipdb.set_trace()
	serverThread = threading.Thread(target = test_server.run_server())
#	ipbd.set_trace()
        serverThread.start()
	
	

	
	
	
	
	
