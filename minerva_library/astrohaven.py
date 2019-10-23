import os
import telnetlib
import socket
import ipdb
import sys
import os
import datetime
import logging
import json
import threading 
import time
import mail
from configobj import ConfigObj
sys.dont_write_bytecode = True
from filelock import FileLock
import utils
import serial
import time
import com

class astrohaven:

	#initialize class by specify configuration file and software base directory
	def __init__(self,config,base):

		self.base_directory = base
		self.config_file = config
		self.load_config()
		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
		self.create_objects()
                self.status = {'Shutter1':'UNKNOWN','Shutter2':'UNKNOWN'}
#                self.status = self.get_status()
				
		self.initialized = False
		self.lock = threading.Lock()
		self.status_lock = threading.RLock()
		# threading.Thread(target=self.write_status_thread).start()
		
		self.estopmail = "The emergency stop is active in the Aqawan, which prevents us from remotely controlling it.\n\n" +\
		"To reset the E-stop:\n\n" +\
		"1) Find the aqawan panel on center of the inside of the north wall. The code to get into the door is the same as the gate code.\n" +\
		"2) A blue light, labeled 'E-stop reset' on the top left of the panel will be flashing. Push it. " +\
		"The light should go off when pressed. If so, you're done. If not, continue to step 3.\n" +\
		"3) One of the E-stops was physically pushed. There's one next to each door and another on the hand paddle to the left of the aqawan panel."+\
		"Find the one that is depressed, turn it counter clockwise until it pops up, then repeat step 2.\n\n" + \
		"Love,\nMINERVA"
		
		self.rainChangeDate = datetime.datetime.utcnow()
		self.lastRain = 0.0

	def load_config(self):
		#create configuration file object
		try:
			config = ConfigObj(self.base_directory+'/config/' + self.config_file)
#			self.PRESSURESENSORCOM_1 = config['Setup']['PRESSURESENSORCOM_1']
#			self.PRESSURESENSORCOM_2 = config['Setup']['PRESSURESENSORCOM_2']
			self.port = config['Setup']['PORT']
			self.baudrate = config['Setup']['BAUDRATE']
#			self.TEMPRHCOM = config['Setup']['TEMPRHCOM']
			self.logger_name = config['Setup']['LOGNAME']
			self.num = config['Setup']['NUM']
			self.id = config['Setup']['ID']
			self.mailsent = False
			self.estopmailsent = False
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit() 
		
		today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')


        def create_objects(self):
            #TODO: test
#            self.pressuresensor1 = com.com(self.PRESSURESENSORCOM_1,night,configfile=configfile)
#            self.pressuresensor2 = com.com(self.PRESSURESENSORCOM_2,night,configfile=configfile)
#            self.temprh = com.com(self.TEMPRHCOM,night,configfile=configfile)
            self.ser = serial.Serial(self.port,baudrate=self.baudrate)            
            self.ser.close()
        
        def nudgeshutter(self, direction, shutter, desiredcounts=1):
                        
            if direction == 'open':
                if shutter == 1: cmd = 'a'
                elif shutter == 2: cmd = 'b'
                else: print  "shutter" + str(shutter) + "not allowed"
            elif direction == 'close':
                if shutter == 1: cmd = 'A'
                elif shutter == 2: cmd = 'B'
                else: print "shutter" + str(shutter) + "not allowed"
            else: print "direction" +str(direction) + "not defined"
            self.ser.open()
            currentcount = 0
            while (currentcount < desiredcounts):
                self.ser.write(cmd)
                currentcount = currentcount + 1 
                time.sleep(0.6)
                status = ''

                while self.ser.inWaiting() > 0: status = self.ser.read(1)
                #print status, direction, shutter
                if direction == 'open':
                    if shutter == 1 and status == 'x': break
                    elif shutter == 2 and status == 'y': break
                if direction == 'close':
                    if shutter == 1 and status == 'X': break
                    elif shutter == 2 and status == 'Y': break

            if status == '0':
                self.status['Shutter1'] = 'CLOSED' 
                self.status['Shutter2'] = 'CLOSED' 
            elif status == '1':
                self.status['Shutter1'] = 'CLOSED' 
                self.status['Shutter2'] = 'NOT CLOSED' 
            elif status == '2':
                self.status['Shutter1'] = 'NOT CLOSED' 
                self.status['Shutter2'] = 'CLOSED' 
            elif status == '3':
                self.status['Shutter1'] = 'NOT CLOSED' 
                self.status['Shutter2'] = 'NOT CLOSED' 
            elif status == 'a':
                self.status['Shutter1'] = 'OPENING' 
            elif status == 'A':
                self.status['Shutter1'] = 'CLOSING' 
            elif status == 'b':
                self.status['Shutter2'] = 'OPENING' 
            elif status == 'B':
                self.status['Shutter2'] = 'CLOSING' 
            elif status == 'X':
                self.status['Shutter1'] = 'CLOSED' 
            elif status == 'x':
                self.status['Shutter1'] = 'OPEN' 
            elif status == 'Y':
                self.status['Shutter2'] = 'CLOSED' 
            elif status == 'y':
                self.status['Shutter2'] = 'OPEN' 
                
            self.ser.close()
         
        def open_shutter(self,shutter, desiredcounts = 20):
            self.nudgeshutter('open',shutter,desiredcounts=desiredcounts)
             
        def close_shutter(self,shutter, desiredcounts = 20):
            self.nudgeshutter('close',shutter,desiredcounts=desiredcounts)
            # TODO: check pressure sensors
            # TODO: if not closed, send an email
                      
        def open_both(self,reverse):
            self.open_shutter(1)
            self.open_shutter(2)
                             
        def close_both(self):
           self.close_shutter(1)
           self.close_shutter(2)   
    
        def get_status(self):
            if self.status['Shutter1'] != 'UNKNOWN' and \
                self.status['Shutter2'] != 'UNKONWN':
                return self.status
            
            self.ser.open()
	    ipdb.set_trace()
            while self.ser.inWaiting() == 0: time.sleep(0.6)
            while self.ser.inWaiting() > 0: status = self.ser.read(1)
            self.ser.close()
            
            if status == '0':
                self.status['Shutter1'] = 'CLOSED' 
                self.status['Shutter2'] = 'CLOSED' 
            elif status == '1':
                self.status['Shutter1'] = 'CLOSED' 
                self.status['Shutter2'] = 'NOT CLOSED' 
            elif status == '2':
                self.status['Shutter1'] = 'NOT CLOSED' 
                self.status['Shutter2'] = 'CLOSED' 
            elif status == '3':
                self.status['Shutter1'] = 'NOT CLOSED' 
                self.status['Shutter2'] = 'NOT CLOSED' 
            elif status == 'a':
                self.status['Shutter1'] = 'OPENING' 
            elif status == 'A':
                self.status['Shutter1'] = 'CLOSING' 
            elif status == 'b':
                self.status['Shutter2'] = 'OPENING' 
            elif status == 'B':
                self.status['Shutter2'] = 'CLOSING' 
            elif status == 'X':
                self.status['Shutter1'] = 'CLOSED' 
            elif status == 'x':
                self.status['Shutter1'] = 'OPEN' 
            elif status == 'Y':
                self.status['Shutter2'] = 'CLOSED' 
            elif status == 'y':
                self.status['Shutter2'] = 'OPEN'                
                                                
            return self.status
            
	def isOpen(self):
		filename = self.base_directory + '/minerva_library/astrohaven' + str(self.num) + '.stat'
		#with FileLock(filename):
		if True:	
			with open(filename,'r') as fh: line = fh.readline().split()
			try:
				lastUpdate = datetime.datetime.strptime(' '.join(line[0:2]),'%Y-%m-%d %H:%M:%S.%f')
				if (datetime.datetime.utcnow() - lastUpdate).total_seconds() > 300:
					self.logger.error("Dome status hasn't updated in 5 minutes; assuming closed")
					return False
				return line[2] == 'True'
			except:
				self.logger.exception("Failed to read aqawan status file")
				return False
		return False

	def heartbeat(self):
            pass
							
if __name__ == '__main__':

        if socket.gethostname() == 'Telcom-PC': base_directory = 'C:\minerva-control'
        else: base_directory = '/home/minerva/minerva-control'
	dome = astrohaven('astrohaven_red.ini',base_directory)
	ipdb.set_trace()
	# while True:
		# print dome.logger_name + ' test program'
		# print ' a. open shutter 1'
		# print ' b. close shutter 1'
		# print ' c. open shutter 2'
		# print ' d. close shutter 2'
		# print ' e. open both shutters'
		# print ' f. close both shutters'
		# print '----------------------------'
		# choice = raw_input('choice:')

		# if choice == 'a':
			# dome.open_shutter(1)
		# elif choice == 'b':
			# dome.close_shutter(1)
		# elif choice == 'c':
			# dome.open_shutter(2)
		# elif choice == 'd':
			# dome.close_shutter(2)
		# elif choice == 'e':
			# dome.open_both()
		# elif choice == 'f':
			# dome.close_both()
		# else:
			# print 'invalid choice'
	
	

