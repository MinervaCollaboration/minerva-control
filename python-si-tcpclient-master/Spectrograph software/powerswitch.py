'''basic power switch control class, writes log to P(1 or 2).log file
create class object by powerswitch(num), where num specify which powerswitch
test program creates powerswitch(1) object and send keyboard commands'''

import time, urllib2, ipdb, datetime, logging, requests
from configobj import ConfigObj
from requests.auth import HTTPBasicAuth

#To Do: change log to appropriate format, log open/close failure by reading status, add more functionality as needed 
class powerswitch:

    #powerswitch class init method, create an aqawan object by passing either P1-P5 to pecify which power switch
    def __init__(self, num, night, configfile=''):

        self.num = num

        #set appropriate parameter based on aqawan_num
        #create configuration file object 
        configObj = ConfigObj(configfile)        
        try:
            config = configObj[self.num]
        except:
            print('ERROR accessing ', self.num, ".", 
               self.num, " was not found in the configuration file", configfile)
            return 

        self.IP = config['Setup']['IP']
        self.PORT = config['Setup']['PORT']
        logger_name = config['Setup']['LOGNAME']
        log_file = 'logs/' + night + '/' + config['Setup']['LOGFILE']
        self.outlets = config['Setup']['OUTLETS']
                
        # setting up powerswitch logger
        fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
        datefmt = "%Y-%m-%dT%H:%M:%S"

        self.logger = logging.getLogger(logger_name)
        formatter = logging.Formatter(fmt,datefmt=datefmt)
        formatter.converter = time.gmtime
        
        fileHandler = logging.FileHandler(log_file, mode='a')
        fileHandler.setFormatter(formatter)

        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(logging.INFO)
        
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(fileHandler)
        self.logger.addHandler(console)


    def send(self,url):

        f = open('authentication.txt','r')
        username = f.readline().strip()
        password = f.readline().strip()
        f.close()
        self.logger.info('Sending command: ' + url)
        response = requests.get(url,auth=(username, password))
        self.logger.info('Response code = ' + str(response.status_code))
        return response
    
    def on(self,outlet):
        url = 'http://' + self.IP + '/outlet?' + str(outlet) + '=ON'
        return self.send(url)

    def off(self,outlet):
        url = 'http://' + self.IP + '/outlet?' + str(outlet) + '=OFF'
        return self.send(url)
    
    def cycle(self,outlet,cycletime=None):

        if cycletime == None:
            url = 'http://' + self.IP + '/outlet?' + str(outlet) + '=CCL'
            return self.send(url)
        else:
            self.off(outlet)
            time.sleep(cycletime)
            return self.on(outlet)  

if __name__ == '__main__':

    p1 = powerswitch('P1','n20150521',configfile='minerva_class_files/powerswitch.ini')
    print p1.cycle(4)
    
