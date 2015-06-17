import urllib, urllib2, datetime, time, logging, json, math
from configobj import ConfigObj
import os, sys, psutil, subprocess, ipdb
#import pwihelpers as pwi
from xml.etree import ElementTree
import minerva_class_files.mail as mail
import minerva_class_files.powerswitch as powerswitch

#HELPER CLASSES
class Status: 
    """
    Contains a node (and possible sub-nodes) in the parsed XML status tree.
    Properties are added to the class by the elementTreeToObject function.
    """

    def __str__(self):
        result = ""
        for k,v in self.__dict__.items():
            result += "%s: %s\n" % (k, str(v))

        return result

def elementTreeToObject(elementTreeNode):
    """
    Recursively convert an ElementTree node to a hierarchy of objects that allow for
    easy navigation of the XML document. For example, after parsing:
      <tag1><tag2>data</tag2><tag1> 
    You could say:
      xml.tag1.tag2   # evaluates to "data"
    """

    if len(elementTreeNode) == 0:
        return elementTreeNode.text

    result = Status()
    for childNode in elementTreeNode:
        setattr(result, childNode.tag, elementTreeToObject(childNode))

    result.value = elementTreeNode.text

    return result



class CDK700:
    def __init__(self, name, night, configfile=''):
        
        self.name = name
        self.night = night

        #check for configuration file 
        if not os.path.isfile(configfile): 
           print('ERROR accessing ',self.name,
                 '.  The configuration file [',configfile, 
                 '] was not found') 
           return

        #create configuration file object 
        configObj = ConfigObj(configfile)
        
        try:
            CDKconfig = configObj[self.name]
        except:
            print('ERROR accessing ', self.name, ".", 
                   self.name, " was not found in the configuration file", configfile)
            return 

        self.HOST = CDKconfig['Setup']['HOST']
        self.PORT = CDKconfig['Setup']['PORT']
        self.imager = CDKconfig['Setup']['IMAGER']
        self.guider = CDKconfig['Setup']['GUIDER']
        self.fau = CDKconfig['Setup']['FAU']
        self.rotatorMailsent=False
        self.nfailed=0
        self.PSNAME = CDKconfig['Setup']['PSNAME']
        self.PSPORT = CDKconfig['Setup']['PSPORT']

        # initialize to the most recent best focus
        if os.path.isfile('focus.txt'):
            f = open('focus.txt','r')
            self.focus = float(f.readline())
            f.close()
        else:
            # if no recent best focus exists, initialize to 25000. (old: current value)
            status = self.getStatus()
            self.focus = 25000.  #status.focuser.position
            
        logger_name = CDKconfig['Setup']['LOGNAME']
        log_file = 'logs/' + night + '/' + CDKconfig['Setup']['LOGFILE']
        self.currentStatusFile = 'current_' + self.name + '.log'

        # setting up telescope logger
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
        
##	self.logger = logging.getLogger(logger_name)
##	formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
##        formatter.converter = time.gmtime
##	fileHandler = logging.FileHandler(log_file, mode='a')
##	fileHandler.setFormatter(formatter)
##	streamHandler = logging.StreamHandler()
##	streamHandler.setFormatter(formatter)
##
##	self.logger.setLevel(logging.DEBUG)
##	self.logger.addHandler(fileHandler)
##	self.logger.addHandler(streamHandler)
    
    # SUPPORT FUNCITONS
    def makeUrl(self, **kwargs):
        """
        Utility function that takes a set of keyword=value arguments
        and converts them into a properly formatted URL to send to PWI.
        For example, calling the function as:
          makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
        will return the string:
          http://127.0.0.1:8080/?device=mount&cmd=move&dec=20+30+40&ra=10+20+30

        Note that spaces have been URL-encoded to "+" characters.
        """

        url = "http://" + self.HOST + ":" + str(self.PORT) + "/?"
        url = url + urllib.urlencode(kwargs.items())
        return url

    def pwiRequest(self, **kwargs):
        """
        Issue a request to PWI using the keyword=value parameters
        supplied to the function, and return the response received from
        PWI.

        For example:
          makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
        will request a slew to J2000 coordinates 10:20:30, 20:30:40, and will
        (under normal circumstances) return the status of the telescope as an
        XML string.
        """
        url = self.makeUrl(**kwargs)
        return urllib.urlopen(url).read()

    def parseXml(self, xml):
        """
        Convert the XML into a smart structure that can be navigated via
        the tree of tag names; e.g. "status.mount.ra"
        """

        return elementTreeToObject(ElementTree.fromstring(xml))


    def pwiRequestAndParse(self, **kwargs):
        """
        Works like pwiRequest(), except returns a parsed XML object rather
        than XML text
        """

        return self.parseXml(self.pwiRequest(**kwargs))

    ### Status wrappers #####################################
    def getStatusXml(self):
        """
        Return a string containing the XML text representing the status of the telescope
        """

        return self.pwiRequest(cmd="getsystem")



    def status(self):

        import xmltodict
        status = xmltodict.parse(self.getStatusXml())

        with open(self.currentStatusFile,'w') as outfile:
            json.dump(status,outfile)

        ipdb.set_trace()

        return status    

    def getStatus(self):
        """
        Return a status object representing the tree structure of the XML text.
        Example: getStatus().mount.tracking --> "False"
        """
        return self.parseXml(self.getStatusXml())

    ### FOCUSER ###
    def focuserConnect(self, port=1):
        """
        Connect to the focuser on the specified Nasmyth port (1 or 2).
        """

        return self.pwiRequestAndParse(device="focuser"+str(port), cmd="connect")

    def focuserDisconnect(self, port=1):
        """
        Disconnect from the focuser on the specified Nasmyth port (1 or 2).
        """

        return self.pwiRequestAndParse(device="focuser"+str(port), cmd="disconnect")

    def focuserMove(self, position, port=1):
        """
        Move the focuser to the specified position in microns
        """

        return self.pwiRequestAndParse(device="focuser"+str(port), cmd="move", position=position)

    def focuserIncrement(self, offset, port=1):
        """
        Offset the focuser by the specified amount, in microns
        """

        return self.pwiRequestAndParse(device="focuser"+str(port), cmd="move", increment=offset)

    def focuserStop(self, port=1):
        """
        Halt any motion on the focuser
        """

        return self.pwiRequestAndParse(device="focuser"+str(port), cmd="stop")

    def startAutoFocus(self):
        """
        Begin an AutoFocus sequence for the currently active focuser
        """
        return self.pwiRequestAndParse(device="focuser", cmd="startautofocus")

    ### ROTATOR ###
    def rotatorMove(self, position, port=1):
        return self.pwiRequestAndParse(device="rotator"+str(port), cmd="move", position=position)

    def rotatorIncrement(self, offset, port=1):
        return self.pwiRequestAndParse(device="rotator"+str(port), cmd="move", increment=offset)

    def rotatorStop(self, port=1):
        return self.pwiRequestAndParse(device="rotator"+str(port), cmd="stop")

    def rotatorStartDerotating(self, port=1):
        return self.pwiRequestAndParse(device="rotator"+str(port), cmd="derotatestart")

    def rotatorStopDerotating(self, port=1):
        return self.pwiRequestAndParse(device="rotator"+str(port), cmd="derotatestop")

    ### MOUNT ###
    def mountConnect(self):
        return self.pwiRequestAndParse(device="mount", cmd="connect")

    def mountDisconnect(self):
        return self.pwiRequestAndParse(device="mount", cmd="disconnect")

    def mountEnableMotors(self):
        return self.pwiRequestAndParse(device="mount", cmd="enable")

    def mountDisableMotors(self):
        return self.pwiRequestAndParse(device="mount", cmd="disable")

    def mountOffsetRaDec(self, deltaRaArcseconds, deltaDecArcseconds):
        return self.pwiRequestAndParse(device="mount", cmd="move", incrementra=deltaRaArcseconds, incrementdec=deltaDecArcseconds)

    def mountOffsetAltAz(self, deltaAltArcseconds, deltaAzArcseconds):
        return self.pwiRequestAndParse(device="mount", cmd="move", incrementazm=deltaAzArcseconds, incrementalt=deltaAltArcseconds)

    def mountGotoRaDecApparent(self, raAppHours, decAppDegs):
        """
        Begin slewing the telescope to a particular RA and Dec in Apparent (current
        epoch and equinox, topocentric) coordinates.

        raAppHours may be a number in decimal hours, or a string in "HH MM SS" format
        decAppDegs may be a number in decimal degrees, or a string in "DD MM SS" format
        """

        return self.pwiRequestAndParse(device="mount", cmd="move", ra=raAppHours, dec=decAppDegs)

    def mountGotoRaDecJ2000(self, ra2000Hours, dec2000Degs):
        """
        Begin slewing the telescope to a particular J2000 RA and Dec.
        ra2000Hours may be a number in decimal hours, or a string in "HH MM SS" format
        dec2000Degs may be a number in decimal degrees, or a string in "DD MM SS" format
        """
        return self.pwiRequestAndParse(device="mount", cmd="move", ra2000=ra2000Hours, dec2000=dec2000Degs)

    def mountGotoAltAz(self, altDegs, azmDegs):
        return self.pwiRequestAndParse(device="mount", cmd="move", alt=altDegs, azm=azmDegs)

    def mountStop(self):
        return self.pwiRequestAndParse(device="mount", cmd="stop")

    def mountTrackingOn(self):
        return self.pwiRequestAndParse(device="mount", cmd="trackingon")

    def mountTrackingOff(self):
        return self.pwiRequestAndParse(device="mount", cmd="trackingoff")

    def mountSetTracking(self, trackingOn):
        if trackingOn:
            self.mountTrackingOn()
        else:
            self.mountTrackingOff()

    def mountSetTrackingRateOffsets(self, raArcsecPerSec, decArcsecPerSec):
        """
        Set the tracking rates of the mount, represented as offsets from normal
        sidereal tracking in arcseconds per second in RA and Dec.
        """
        return self.pwiRequestAndParse(device="mount", cmd="trackingrates", rarate=raArcsecPerSec, decrate=decArcsecPerSec)

    def mountSetPointingModel(self, filename):
        return self.pwiRequestAndParse(device="mount", cmd="setmodel", filename=filename)

    ### M3 ###
    def m3SelectPort(self, port):
        return self.pwiRequestAndParse(device="m3", cmd="select", port=port)

    def m3Stop(self):
        return self.pwiRequestAndParse(device="m3", cmd="stop")

    def killPWI(self):
        for p in psutil.process_iter():
            try:
                pinfo = p.as_dict(attrs=['pid','name'])
                if pinfo['name'] == 'PWI.exe':
                    self.logger.info('Killing PWI')
                    p.kill()
                    return
            except psutil.Error:
                pass
            
    def restartPWI(self, email=True):
        self.killPWI()
        self.logger.info('PWI not running, starting now')
        self.startPWI(email=email)

    def startPWI(self, email=True):
        for p in psutil.process_iter():
            try:
                pinfo = p.as_dict(attrs=['pid','name'])
                if pinfo['name'] == 'PWI.exe':
                    self.logger.info('PWI already running')
                    return
            except psutil.Error:
                pass

        self.logger.info('PWI not running, starting now')
        try:
            subprocess.Popen(["C:\Program Files\PlaneWave Instruments\PlaneWave Interface\PWI.exe"])
        except:
            subprocess.Popen(["C:\Program Files (x86)\PlaneWave Instruments\PlaneWave Interface\PWI.exe"])

        if email: mail.send("PWI restarted on " + self.name,"Autofocus parameters will not be respected until manually run once") 

        time.sleep(5)   
            
    # additional higher level routines
    def initialize(self):

        self.logger.info('Starting PWI')
        self.startPWI()

        # turning on mount tracking
        self.logger.info('Connecting to mount')
        self.mountConnect()

        self.logger.info('Enabling motors')
        self.mountEnableMotors()
        
        # turning on mount tracking
        self.logger.info('Turning mount tracking on')
        self.mountTrackingOn()

        self.focuserConnect()
    
        # turning on rotator tracking
        self.logger.info('Turning rotator tracking on')
        self.rotatorStartDerotating()

    def shutdown(self):
        self.rotatorStopDerotating()
        self.focuserDisconnect()
        self.mountTrackingOff()
        self.mountDisconnect()
        self.mountDisableMotors()

    def powercycle(self):
        
        ps = powerswitch.powerswitch(self.PSNAME,self.night,'minerva_class_files/powerswitch.ini')
        ps.cycle(self.PSPORT, cycletime=60)
        time.sleep(30) # wait for the panel to initialize
        
    def recover(self):

        self.nfailed = self.nfailed + 1
        if self.nfailed >= 3:  
            body = "Dear benevolent humans,\n\n" + \
                   "I'm broken. I power cycled myself, but I need your help to finish the recovery (and investigate):\n\n" + \
                   "1) Make sure the telescope is connected, the drives are enabled, and the tracking is off.\n" + \
                   "2) Home the telescope\n" + \
                   "   * If this fails, you may need to power cycle the 'T# panel' and start over:\n" + \
                   "   * T1 - 192.168.1.36\n" + \
                   "   * T2 - 192.168.1.37\n" + \
                   "   * T3 - 192.168.1.38\n" + \
                   "   * T4 - 192.168.1.39\n" + \
                   "3) Make sure the rotator is connected and the 'Alt Az Derotate' is off.\n" + \
                   "4) Home the rotator\n" + \
                   "5) Check the rotator zero points (PWI rotate tab)\n" + \
                   "   * T1 - 56.42\n" + \
                   "   * T2 - 182.70\n" + \
                   "   * T3 - 198.75\n" + \
                   "   * T4 - 224.18\n" + \
                   "   If those aren't the same, don't change them, but note it, and don't be surprised if you get an email after the first science image that the rotator is screwed up.\n" + \
                   "6) Start an autofocus sequence, wait 30 seconds, and cancel it (if you don't do this, the scripted autofocus will use the default values which don't span enough range).\n" + \
                   "7) type 'c' in the command window to resume operations.\n\n" + \
                   "Love,\n" + \
                   "MINERVA"
            
            self.logger.error("Telescope has failed more than 3 times; something probably seriously wrong...")
            mail.send(self.name + " has failed " + str(self.nfailed) + " times",body,level='serious')

            try: self.shutdown()
            except: pass
            self.killPWI()
            self.powercycle()
            self.startPWI()
            self.mountConnect()
            self.mountEnableMotors()
            self.focuserConnect()
            
#            self.initialize()           
    
            ipdb.set_trace()

        self.logger.info('Telescope in error state; attempting recovery')

        try: self.shutdown()
        except: pass
        self.restartPWI()
        self.initialize()
            

    def inPosition(self, ra=None, dec=None, alt=None, az=None):
        # Wait for telescope to complete motion
        timeout = 360.0
        start = datetime.datetime.utcnow()
        elapsedTime = 0
        time.sleep(0.25) # needs time to start moving
        telescopeStatus = self.getStatus()
        self.logger.info('Waiting for telescope to finish slew; moving = ' + telescopeStatus.mount.moving)
        while telescopeStatus.mount.moving == 'True' and elapsedTime < timeout:
            time.sleep(0.1)
            elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
            telescopeStatus = self.getStatus()
            if telescopeStatus.mount.moving == 'False':
                time.sleep(1)
                telescopeStatus = self.getStatus()
                if telescopeStatus.mount.moving == 'True':
                    self.logger.error("Telescope moving after it said it was done")

            if telescopeStatus.mount.alt_motor_error_code <> '0':
                self.logger.error('Error with altitude drive: ' + telescopeStatus.mount.alt_motor_error_message)
                self.recover()

            if telescopeStatus.mount.azm_motor_error_code <> '0':
                self.logger.info('Error with azmimuth drive: ' + telescopeStatus.mount.azm_motor_error_message)
                self.recover()

        self.logger.info('Waiting for rotator to finish slew; goto_complete = ' + telescopeStatus.rotator.goto_complete)
        while telescopeStatus.rotator.goto_complete == 'False' and elapsedTime < timeout:
            time.sleep(0.1)
            elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
            telescopeStatus = self.getStatus()
            if telescopeStatus.rotator.goto_complete == 'True':
                time.sleep(1)
                telescopeStatus = self.getStatus()
                if telescopeStatus.rotator.goto_complete == 'False':
                    self.logger.error("Rotator moving after it said it was done")               
        
        if telescopeStatus.mount.on_target == 'True' and telescopeStatus.rotator.goto_complete == 'True':
            self.logger.info('Telescope finished slew')
            return True
        else:
            self.logger.error('Telescope failed to slew')
            return False

    def acquireTarget(self,ra,dec,pa=None):
        self.initialize()
    
        self.logger.info("Starting slew to J2000 " + str(ra) + ',' + str(dec))
        self.mountGotoRaDecJ2000(ra,dec)

        if pa <> None:
            self.logger.info("Slewing rotator to PA=" + str(pa) + ' deg')
            self.rotatorMove(pa)

        if self.inPosition():
            self.logger.info("Finished slew to J2000 " + str(ra) + ',' + str(dec))
        else:        
            self.logger.error("Slew failed to J2000 " + str(ra) + ',' + str(dec) + '; attempting recovery')
            self.recover()
            self.acquireTarget(ra,dec,pa=pa)
            return

    def park(self):
        # park the scope (no danger of pointing at the sun if opened during the day)
        parkAlt = 45.0
        parkAz = 0.0 

        self.logger.info('Parking telescope (alt=' + str(parkAlt) + ', az=' + str(parkAz) + ')')
        self.mountGotoAltAz(parkAlt, parkAz)
        self.inPosition()

        self.logger.info('Turning mount tracking off')
        self.mountTrackingOff()
    
        self.logger.info('Turning rotator tracking off')
        self.rotatorStopDerotating()

    def recoverFocuser(self):
        timeout = 60.0

        self.logger.info('Beginning focuser recovery')

        self.focuserStop()
        self.rotatorStopDerotating()
        self.focuserDisconnect()
        self.restartPWI(email=False)
        time.sleep(5)

        self.initialize()
        self.focuserConnect()
        self.focuserMove(self.focus)
        t0 = datetime.datetime.utcnow()

        status = self.getStatus()
        while status.focuser.moving == 'True':
            self.logger.info('Focuser moving (' + str(status.focuser.position) + ')')
            time.sleep(0.3)
            status = self.getStatus()
            if (datetime.datetime.utcnow() - t0).total_seconds() > timeout:
                self.logger.error('Focus timed out')
                mail.send("Focuser timed out on " + str(self.name),"Try powercycling?",level='serious')
                return
        self.logger.info("Focuser recovered")
        

    def autoFocus(self):

        timeout = 180.0

        self.initialize()

        self.logger.info('Connecting to the focuser')
        self.focuserConnect()

        nominalFocus = self.focus
        self.logger.info('Moving to nominal focus (' + str(nominalFocus) + ')')
        self.focuserMove(nominalFocus) # To get close to reasonable. Probably not a good general postion
        time.sleep(5.0)
        status = self.getStatus()
        while status.focuser.moving == 'True':
            self.logger.info('Focuser moving (' + str(status.focuser.position) + ')')
            time.sleep(0.3)
            status = self.getStatus()
            
        self.logger.info('Finished move to focus (' + str(status.focuser.position) + ')')


        self.logger.info('Starting Autofocus')
        t0 = datetime.datetime.utcnow()
        self.startAutoFocus()
        status = self.getStatus()
        while status.focuser.auto_focus_busy == 'True':
            time.sleep(1)
            status = self.getStatus()
            if (datetime.datetime.utcnow() - t0).total_seconds() > timeout:
                self.logger.error('autofocus timed out')
                self.recoverFocuser()
                self.autoFocus()
                return
        
        status = self.getStatus()
        self.focus = float(status.focuser.position)
        alt = str(float(status.mount.alt_radian)*180.0/math.pi)

        try:
            tm1 = str(status.temperature.primary)
            tm2 = str(status.temperature.secondary)
            tm3 = str(status.temperature.m3)
            tamb = str(status.temperature.ambient)
            tback = str(status.temperature.backplate)
        except:
            tm1 = 'UNKNOWN'
            tm2 = 'UNKNOWN'
            tm3 = 'UNKNOWN'
            tamb = 'UNKNOWN'
            tback = 'UNKNOWN'
        
        self.logger.info('Updating best focus to ' + str(self.focus) + ' (TM1=' + tm1 + ', TM2=' + tm2 + ', TM3=' + tm3 + ', Tamb=' + tamb + ', Tback=' + tback + ', alt=' + alt + ')' )
        f = open('focus.txt','w')
        f.write(str(self.focus))
        f.close()
        
        self.logger.info('Finished autofocus')


if __name__ == "__main__":
    t3 = CDK700('T3', 'n20150530',configfile = 'minerva_class_files/telescope.ini')
