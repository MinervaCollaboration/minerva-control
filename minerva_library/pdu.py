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

from pysnmp.entity.rfc3413.oneliner import cmdgen  
from pysnmp.proto import rfc1902
import logging
import os
import os.path
import socket
import utils

class PduError(Exception):
    None
    
class pdu():
    class __PduParameters():
        def __init__(self,config,base):
		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)

	def load_config(self):
		try:
			configObj = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.ip = configObj['IP']
			self.port = configObj['PORT']
			self.logger_name = configObj['LOGNAME']
			outlets = configObj['OUTLETS']
                        self.outlet_names = {}
                        outletnum = 0
                        for outlet in outlets:
                            outletnum += 1
                            self.outlet_names[outletnum] = outlet
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()

		self.community = 'private'
		self.retries = 5
                #S Increasing timeout from 1 to 3 seconds, had it hit this and throw errors a few times
		self.timeout = 5
		self.getStatusAllOutlets = (1,3,6,1,4,1,318,1,1,4,2,2,0)
		self.outletBaseOID = [1,3,6,1,4,1,318,1,1,4,4,2,1,3]
		self.setOutletStates = {'On':1,'Off':2,'Reboot':3}

#		self.logger.info('PDU started up on '+socket.gethostname()+' with:')
#		self.logger.info('    IP = '+self.ip)

		keys = self.outlet_names.keys()
		keys.sort()
#		for curkey in keys:
#			self.logger.info('    Port '+str(curkey)+' = '+self.outlet_names[curkey])

		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
			today = today + datetime.timedelta(days=1)
		self.night = 'n' + today.strftime('%Y%m%d')

    def __init__(self, config, base):
        self.__pdu_params = self.__PduParameters(config, base)
        self.outlets = {}
        #create each outlet and attach it to its appropriate outlet name as a functions
        for cur_outlet_number in self.__pdu_params.outlet_names.keys():
            cur_outlet_name = self.__pdu_params.outlet_names[cur_outlet_number]
            if cur_outlet_name == None:
                cur_outlet_name = 'outlet'+str(cur_outlet_number)
                self.__pdu_params.outlet_names[cur_outlet_number] = cur_outlet_name
            new_outlet = self.__PduOutlet( self.__pdu_params, 
                                           cur_outlet_number, 
                                           cur_outlet_name, self.status ) 
            exec "self." + cur_outlet_name + '= new_outlet'
            exec "self.outlets[" + str(cur_outlet_number) + '] = new_outlet'
#        self.print_status_with_names()

    def __call__(self):
        self.print_status_with_names()
        return self.status()

    def print_status_with_names(self):
        max_name_length = max([len(a) for 
                               a in self.__pdu_params.outlet_names.values()])
        for i,status in enumerate(self.status()):
            outlet_number = i+1
            if os.name == 'posix':
                reset_color_string = '\033[0;0m'
                if status == 'On':  
                    color_string = '\033[1;32m'
                elif status == 'Off':
                    color_string = '\033[0;31m'
                else:
                    color_string = ''
            elif os.name == 'nt':  # these colors sequences not supported in cygwin
                color_string = ''
                reset_color_string = ''
            else:
                color_string = ''
                reset_color_string = ''

            print ( color_string + str(outlet_number)+'  '+
                    (('%'+str(max_name_length)+'s') % 
                     self.__pdu_params.outlet_names[outlet_number]) + '  ' + status + reset_color_string)

    def status(self):
#        self.logger.info('status request')
        return self.__snmpGet__(self.__pdu_params.getStatusAllOutlets)
    
    def __snmpGet__(self,oid):
        ( errorIndication, errorStatus, 
          errorIndex, varBinds ) = cmdgen.CommandGenerator().getCmd(
            cmdgen.CommunityData('test-agent', 'public'),
            cmdgen.UdpTransportTarget((self.__pdu_params.ip,
                                       self.__pdu_params.port)),
            oid,(('SNMPv2-MIB', 'sysObjectID'), 0))
        if errorIndication:
            raise PduError(errorIndication)
        else:
            if errorStatus:
                raise PduError('%s at %s\n' % 
                               (errorStatus.prettyPrint(),
                                errorIndex and varBinds[int(errorIndex)-1] or '?'))
            else:
                for name, val in varBinds:
                    if name == oid:
                        return str(val).split()

    class __PduOutlet():
        def __init__(self, pdu_params, outlet_number, outlet_name, status_function):
            self.__pdu_params = pdu_params
            self.outlet_number = outlet_number
            self.outlet_name = outlet_name
            self.__all_outlet_status_function = status_function
            
        def __call__(self,request=None):
            if request != None:
                if request:
                    self.on()
                else:
                    self.off()
            return self.status()
        
        def __snmpSet__(self,oid,val):
            errorIndication, errorStatus, \
                errorIndex, varBinds = cmdgen.CommandGenerator().setCmd(
                cmdgen.CommunityData('private', 'private', 1), 
                cmdgen.UdpTransportTarget((self.__pdu_params.ip, self.__pdu_params.port)), 
                (oid, rfc1902.Integer(str(val))))
            if errorIndication:
                raise PduError(errorIndication)
            else:
                if errorStatus:
                    raise PduError('%s at %s\n' % 
                                   (errorStatus.prettyPrint(),
                                    errorIndex and varBinds[int(errorIndex)-1] or '?'))
                else:
                    for name, val in varBinds:
                        if name == oid:
                            return str(val).split()

        def on(self):
#            self.logger.info("ON requested for "+self.outlet_name+
#                         " on outlet # "+str(self.outlet_number))
            self.__snmpSet__(self.__pdu_params.outletBaseOID+[self.outlet_number],
                             self.__pdu_params.setOutletStates['On'])
            return self.status()
        
        def off(self):
#            self.logger.info("OFF requested for "+self.outlet_name+
#                         " on outlet # "+str(self.outlet_number))
            self.__snmpSet__(self.__pdu_params.outletBaseOID+[self.outlet_number],
                             self.__pdu_params.setOutletStates['Off'])
            return self.status()

        def status(self):
            outlet_status = self.__all_outlet_status_function()[self.outlet_number - 1]
            if outlet_status == 'On':
                return True
            elif outlet_status == 'Off':
                return False
            raise PduError("Unrecognized PDU state error")


if __name__ == '__main__':
    pdu1 = pdu('apc_1.ini','/home/minerva/minerva-control')
    pdu1.print_status_with_names()
    ipdb.set_trace()
	
	
	
