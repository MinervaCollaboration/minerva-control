import time
import urllib
import urllib2
from xml.etree import ElementTree

def main():
    """
    Tests and examples for the pwi2control library
    """

    pwi2 = PWI2(host="192.168.1.70", port=44444)

    # We can generate a URL using keyword arguments in Python:
    url = pwi2.makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
    print "Sample URL:", url
    print

    # We can also generate that URL, send the request to PWI, and retrieve the response XML
    print "Turning tracking on..."
    response = pwi2.pwiRequest(device="mount", cmd="trackingon")
    print "Response (truncated):", response[:500], "..."
    print

    # Raw XML status text can be retrieved using a simple wrapper function
    xml = pwi2.getStatusXml()
    print "XML Resonse (truncated):", response[:500], "..."
    print

    # We can also use a function that returns an object representing the XML
    # that makes it more natural to navigate through the XML structure
    status = pwi2.getStatus()
    print "Current status:"
    print "  Focuser1 connected:", status.focuser1.connected
    print "  Focuser1 position:", status.focuser1.position
    print "  Rotator1 connected:", status.rotator1.connected
    print "  Rotator1 position:", status.rotator1.position
    print "  M3 Port:", status.m3.port
    print "  Mount connected:", status.mount.connected
    print "  Mount tracking:", status.mount.tracking
    print "  Mount RA (rads):", status.mount.ra_radian
    print "  Mount Dec (rads):", status.mount.dec_radian

    # Note that each field is currently returned as a string. If you want to
    # do operations on the values, you need to convert the values first
    ra_hours = float(status.mount.ra_radian) * 180/3.14159 / 15
    dec_degs = float(status.mount.dec_radian) * 180/3.14159
    print "  Mount RA (hours):", ra_hours
    print "  Mount Dec (degs):", dec_degs
    print

    # Rather than making low-level calls to pwiRequest(), we can write simple
    # wrapper functions for all of the major commands
    print "Connecting to focuser on Nasmyth port 1..."
    pwi2.focuserConnect(1)
    print "Connected:", pwi2.getStatus().focuser1.connected

    print "Disconnecting from focuser on Nasmyth port 1..."
    pwi2.focuserDisconnect(1)
    print "Connected:", pwi2.getStatus().focuser1.connected

    print "Turning off tracking..."
    pwi2.mountTrackingOff()


######################################################################

class PWI2:
    def __init__(self, host="127.0.0.1", port=8080):
        self.host = host
        self.port = port

        self.timeoutSeconds = 3

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

        url = "http://" + self.host + ":" + str(self.port) + "/?"
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
        return urllib2.urlopen(url, timeout=self.timeoutSeconds).read()

    def pwiRequestAndParse(self, **kwargs):
        """
        Works like pwiRequest(), except returns a parsed XML object rather
        than XML text
        """

        return self.parseXml(self.pwiRequest(**kwargs))

    def parseXml(self, xml):
        """
        Convert the XML into a smart structure that can be navigated via
        the tree of tag names; e.g. "status.mount.ra"
        """

        return self.elementTreeToObject(ElementTree.fromstring(xml))

    ### Status wrappers #####################################

    def getStatusXml(self):
        """
        Return a string containing the XML text representing the status of the telescope
        """

        return self.pwiRequest(cmd="getsystem")

    def getStatus(self):
        """
        Return a status object representing the tree structure of the XML text.
        Example: getStatus().mount.tracking --> "False"
        """

        return self.parseXml(self.getStatusXml())

    ### High-level command wrappers begin here ##############

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

    def mountGotoRaDecApparentWithRates(self, raAppHours, decAppDegs, raArcsecPerSec, decArcsecPerSec):
        return self.pwiRequestAndParse(
                device="mount", 
                cmd="move", 
                ra=raAppHours, 
                dec=decAppDegs,
                rarate=raArcsecPerSec,
                decrate=decArcsecPerSec)

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

    def mountJog(self, axis1DegsPerSec, axis2DegsPerSec):
        return self.pwiRequestAndParse(device="mount", cmd="jog", axis1rate=axis1DegsPerSec, axis2rate=axis2DegsPerSec)

    def mountFindHome(self):
        return self.pwiRequestAndParse(device="mount", cmd="findhome")


    ### M3 ###

    def m3SelectPort(self, port):
        return self.pwiRequestAndParse(device="m3", cmd="select", port=port)

    def m3Stop(self):
        return self.pwiRequestAndParse(device="m3", cmd="stop")



    ### XML Parsing Utilities ##################################

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

    def elementTreeToObject(self, elementTreeNode):
        """
        Recursively convert an ElementTree node to a hierarchy of objects that allow for
        easy navigation of the XML document. For example, after parsing:
          <tag1><tag2>data</tag2><tag1> 
        You could say:
          xml.tag1.tag2   # evaluates to "data"
        """

        if len(elementTreeNode) == 0:
            return elementTreeNode.text

        result = self.Status()
        for childNode in elementTreeNode:
            setattr(result, childNode.tag, self.elementTreeToObject(childNode))

        result.value = elementTreeNode.text

        return result



if __name__ == "__main__":
    main()
