'''basic power switch control class, writes log to P(1 or 2).log file
create class object by powerswitch(num), where num specify which powerswitch
test program creates powerswitch(1) object and send keyboard commands'''

import time, urllib2, ipdb, datetime, logging, requests
import selenium
from selenium import webdriver
from configobj import ConfigObj
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth

#To Do: change log to appropriate format, log open/close failure by reading status, add more functionality as needed 
class dynapower:

    #powerswitch class init method, create an aqawan object by passing either P1-P5 to pecify which power switch
    def __init__(self, night, base='', configfile='',driverfile='chromedriver.exe',browser=False):

        #set appropriate parameter based on aqawan_num
        #create configuration file object 
        configObj = ConfigObj(base+'/config/'+configfile)
        try:
            config = configObj
        except:
            print('ERROR accessing ' + configfile)
            return 

        #ipdb.set_trace()
        self.IP = config['IP']
        self.PORT = config['PORT']
        logger_name = config['LOGNAME']
        log_file = 'log/' + night + '/' + config['LOGFILE']
        self.outlets = config['OUTLETS']
        self.username = config['USER']
        self.password = config['PASSWORD']
        self.base = base
        self.driverfile = driverfile
        
                
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

        #S Stuff for status check
        #S I added the browser boolean in case there are dynapower instances that do not require
        #S a status check at all, which will keep the number of open browsers to a minimum. This feels
        #S just about as hacky as the whole thing already, but the whole thing already is.
        self.browserOpen = False
        if browser:
            self.browserOpen = True
            #S Open the browser, make sure chromedriver.exe is in /dependencies.
            self.browser = selenium.webdriver.Chrome(base+'/dependencies/'+driverfile)
            #S Navigate to the outlet.htm page of the PDU, with the username and password for
            #S the basic http authentication.
            self.browser.get('http://'+self.username+':'+self.password+'@'+self.IP+'/outlet.htm')
            #S Give it a minute to run all the JavaScript for the page.
            time.sleep(2)
            #S Leave the browser open. Think about creating clean up function to close browsers, etc.
            
    #S Update the status dictionary for hte PDU
    def updateStatus(self):
        self.status = {}
        #S This is a try just to catch if the browser is still open. If anything throws,
        #S it will open a new browser.
        try:
            #S This is to ensure that we are still at the correct url, which will contain our IP and
            #S the orrect page.
            if (self.IP+'/outlet.htm') in self.browser.current_url:
                #S The table elements always start at 'A11' (those are ones, so 'A-eleven') and got to 'A18'.
                #S We want to loop through them, incrementing as we go through keys.
                outletidnum = 10
                #S For all of our keys(or outlets)
                for key in self.outlets.keys():
                    #S Up the id number
                    outletidnum += 1
                    #S Make appropriate string
                    outletid = 'A'+str(outletidnum)
                    #S Find that sucker
                    self.status[key] = self.browser.find_element_by_id(outletid).text
            #S If our browser is open, but we are at the wrong address, we'll re-get our outlet page,
            #S Wait on scripts, then try again.
            else:
                self.browser.get('http://'+self.username+':'+self.password+'@'+self.IP+'/outlet.htm')
                time.sleep(2)
                self.updateStatus()
        #S If we find an exception, most likely due to browser being closed. Reopen it.
        #NOTE The navigation will occur in the next iteration.
        except:
            self.browser = selenium.webdriver.Chrome(self.base+'/dependencies/'+self.driverfile)
            self.updateStatus()
            
        #DEBUG        
        for key in self.status.keys():
            print key,self.status[key],type(self.status[key])


    def send(self,url):

        f = open('credentials/dynapower.txt','r')
        username = f.readline().strip()
        password = f.readline().strip()
        f.close()
        self.logger.info('Sending command: ' + url)
        response = requests.get(url,auth=(username, password))
        self.logger.info('Response code = ' + str(response.status_code))
        return response

    def getoutletstr(self,outlet):
        outletstr = ''
        for i in range(8):
            if str(i+1) == str(outlet): outletstr = outletstr + '1'
            else: outletstr = outletstr + '0'
        outletstr = outletstr + '00000000' + '00000000'
        return outletstr
    
    def on(self,outlet):
        outletstr = self.getoutletstr(self.outlets[outlet])
        url = 'http://' + self.IP + '/ons.cgi?led=' + outletstr
        return self.send(url)

    def off(self,outlet):
        outletstr = self.getoutletstr(self.outlets[outlet])
        url = 'http://' + self.IP + '/offs.cgi?led=' + outletstr
        return self.send(url)
    
    def cycle(self,outlet,cycletime=None):

        if cycletime == None:
            outletstr = self.getoutletstr(self.outlets[outlet])
            url = 'http://' + self.IP + '/offon.cgi?led=' + outletstr
            return self.send(url)
        else:
            self.off(outlet)
            time.sleep(cycletime)
            return self.on(outlet)

#    def status(self):
 #       url = 'http://' + self.IP + '/'


        

if __name__ == '__main__':
    ipdb.set_trace()
    d2 = dynapower('n20150824',base = 'C:/minerva-control/',configfile='dynapower_2.ini',browser=True)
    
    
    
