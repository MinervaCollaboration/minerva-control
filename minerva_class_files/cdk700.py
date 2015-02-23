import urllib, urllib2, datetime, time, logging, json
from configobj import ConfigObj
import os, sys, ipdb
#import pwihelpers as pwi
from xml.etree import ElementTree

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
        logger_name = CDKconfig['Setup']['LOGNAME']
        log_file = 'logs/' + night + '/' + CDKconfig['Setup']['LOGFILE']
        self.currentStatusFile = 'current_' + self.name + '.log'

        # setting up telescope logger
	self.logger = logging.getLogger(logger_name)
	formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
	fileHandler = logging.FileHandler(log_file, mode='a')
	fileHandler.setFormatter(formatter)
	streamHandler = logging.StreamHandler()
	streamHandler.setFormatter(formatter)

	self.logger.setLevel(logging.DEBUG)
	self.logger.addHandler(fileHandler)
	self.logger.addHandler(streamHandler)
    
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

    # additional higher level routines
    def initialize(self):

        # turning on mount tracking
        self.logger.info('Connecting to mount')
        self.mountConnect()
        
        # turning on mount tracking
        self.logger.info('Turning mount tracking on')
        self.mountTrackingOn()
    
        # turning on rotator tracking
        self.logger.info('Turning rotator tracking on')
        self.rotatorStartDerotating()

    def attemptRecovery(self):
        self.logger.info('Telescope in error state; attempting recovery')
        self.mountEnableMotors()
#        self.

    def inPosition(self):
        # Wait for telescope to complete motion
        timeout = 60.0
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
                self.attemptRecovery()

            if telescopeStatus.mount.azm_motor_error_code <> '0':
                self.logger.info('Error with azmimuth drive: ' + telescopeStatus.mount.azm_motor_error_message)
                self.attemptRecovery()
                
        
        if telescopeStatus.mount.on_target:
            self.logger.info('Telescope finished slew')
            return True
        else:
            self.logger.error('Telescope failed to slew')
            return False

    def acquireTarget(self,ra,dec):
        self.initialize()
    
        self.logger.info("Starting slew to J2000 " + str(ra) + ',' + str(dec))
        self.mountGotoRaDecJ2000(ra,dec)

        if self.inPosition():
            self.logger.info("Finished slew to J2000 " + str(ra) + ',' + str(dec))
        else:
            self.logger.error("Slew failed to J2000 " + str(ra) + ',' + str(dec))

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

    def autoFocus(self):

        self.initialize()

        nominalFocus = 25500
        self.focuserConnect()

        self.logger.info('Moving to nominal focus (' + str(nominalFocus) + ')')
        self.focuserMove(nominalFocus) # To get close to reasonable. Probably not a good general postion
        status = self.getStatus()
        while status.focuser.moving == 'True':
            time.sleep(0.3)
            status = self.getStatus()
        self.logger.info('Finished move to focus (' + str(status.focuser.position) + ')')


        self.logger.info('Starting Autofocus')
        self.startAutoFocus()
        status = self.getStatus()
        while status.focuser.auto_focus_busy == 'True':
            time.sleep(1)
            status = self.getStatus()
        self.logger.info('Finished autofocus')


if __name__ == "__main__":
    t3 = CDK700('T3', configfile = 'twotelescopeconfig.ini')
