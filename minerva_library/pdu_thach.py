from configobj import ConfigObj
import logging
import utils
import sys
import datetime
import requests


class pdu(object):

    def __init__(self, config, base):
        self.config_file = config
        self.base_directory = base
        self.load_config()
        self.logger = utils.setup_logger(self.base_directory, self.night, self.logger_name)
        self.url = "http://"+self.ip+'/cmd.cgi?'

    def load_config(self):
        """
        Loads in the pertinent PDU information
        """
        try:
            # All necessary for referencing our PDUs
            configObj = ConfigObj(self.base_directory + '/config/' + self.config_file)
            self.ip = configObj['IP']
	    self.port = configObj['PORT']
	    self.logger_name = configObj['LOGNAME']
            self.outlets = configObj["OUTLETS"]
        except:
            print("ERROR accessing configuration file: " + self.config_file)

            sys.exit()

        self.community = 'private'
        self.retries = 5
        self.timeout = 5
        # commands for constructing URLs
        self.setCommands = {'on':"$A3 %d 1", 'off':"$A3 %d 0", 'reboot':"$A4 %d", 'status':"$A5"}
        
        today = datetime.datetime.utcnow()
	if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
	    today = today + datetime.timedelta(days=1)
	self.night = 'n' + today.strftime('%Y%m%d')

    def print_status_with_names(self):
        """
        Print all of the outlet names with their status
        """
        # For each outlet, print the status
        for n,outlet in enumerate(self.outlets):
            print(outlet+': '+self.status(n))

    def status(self, outlet=None):
        """
        Get the status of an entire PDU or just one outlet
        **kwarg outlet: default is none, otherwise is int outlet number
                        of the outlet which you want the status of
        *NOT ZERO BASED INDEX

        Returns: str of int(s) corresponding to each or one outlet, 1=on 0=off
        """
        # Construct url for command
        cmdStr = self.url + self.setCommands['status']
        # returns a comma dilleniated string where the outlet order is reversed
        # so, parse the string into a list, select the needed part, and reverse it
        response = self.cmd(cmdStr).text.split(',')[1][::-1]

        # If wants status of a particular outlet, return that, otherwise, return all
        if outlet+2:
            return response[outlet]
        else:
            return response

    def on(self, outlet):
        """
        Turns a particular outlet on
        int outlet: outlet number you would like to turn on
        *NOT ZERO BASED INDEX

        returns: boolean, true for success
        """
        # Construct URL for command
        cmdStr = self.url + self.setCommands['on'] %outlet
        # Execute command, return true if success
        return self.cmd(cmdStr).text.__contains__("$A0")

    def off(self, outlet):
        """
        Turns a particular outlet off
        int outlet: outlet number you would like to turn off
        *NOT ZERO BASED INDEX

        returns: boolean, true for success
        """
        cmdStr = self.url + self.setCommands['off'] %outlet
        return self.cmd(cmdStr).text.__contains__("$A0")

    def reboot(self, outlet):
        """
        Reboots a particular outlet
        int outlet: outlet number you would like to reboot
        *NOT ZERO BASED INDEX

        returns: boolean, true for success
        """
        # construct URL for command
        cmdStr = self.url + self.setCommands['reboot'] %outlet
        # Run command, return true if success
        return self.cmd(cmdStr).text.__contains__("$A0")

    def cmd(self, url):
        """
        Execute command to PDU
        """
        # Credentials to access our PDUs
        f = open(self.base_directory + '/credentials/authentication.txt','r')
        f.readline()
        f.readline()
        username = f.readline().strip()
        password = f.readline().strip()
        f.close()

        # Execute the command and retrieve response using requests
        return requests.get(url, auth=(username, password))

    
#TODO: create on/off all methods (simply a for loop)
#TODO: create logger for all significant events in this code (MINERVA has not done this yet)
