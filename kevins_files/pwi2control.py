import time
import urllib
from xml.etree import ElementTree

HOST = "127.0.0.1" # Localhost
PORT = 8080

def main():
    """
    Tests and examples for the pwi2control library
    """

    # We can generate a URL using keyword arguments in Python:
    url = makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
    print "Sample URL:", url
    print

    # We can also generate that URL, send the request to PWI, and retrieve the response XML
    print "Turning tracking on..."
    response = pwiRequest(device="mount", cmd="trackingon")
    print "Response (truncated):", response[:500], "..."
    print

    # Raw XML status text can be retrieved using a simple wrapper function
    xml = getStatusXml()
    print "XML Resonse (truncated):", response[:500], "..."
    print

    # We can also use a function that returns an object representing the XML
    # that makes it more natural to navigate through the XML structure
    status = getStatus()
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
    focuserConnect(1)
    print "Connected:", getStatus().focuser1.connected

    print "Disconnecting from focuser on Nasmyth port 1..."
    focuserDisconnect(1)
    print "Connected:", getStatus().focuser1.connected

    print "Turning off tracking..."
    mountTrackingOff()


######################################################################

def makeUrl(**kwargs):
    """
    Utility function that takes a set of keyword=value arguments
    and converts them into a properly formatted URL to send to PWI.
    For example, calling the function as:
      makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
    will return the string:
      http://127.0.0.1:8080/?device=mount&cmd=move&dec=20+30+40&ra=10+20+30

    Note that spaces have been URL-encoded to "+" characters.
    """

    url = "http://" + HOST + ":" + str(PORT) + "/?"
    url = url + urllib.urlencode(kwargs.items())
    return url

def pwiRequest(**kwargs):
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

    url = makeUrl(**kwargs)
    return urllib.urlopen(url).read()

def pwiRequestAndParse(**kwargs):
    """
    Works like pwiRequest(), except returns a parsed XML object rather
    than XML text
    """

    return parseXml(pwiRequest(**kwargs))

def parseXml(xml):
    """
    Convert the XML into a smart structure that can be navigated via
    the tree of tag names; e.g. "status.mount.ra"
    """

    return elementTreeToObject(ElementTree.fromstring(xml))

### Status wrappers #####################################

def getStatusXml():
    """
    Return a string containing the XML text representing the status of the telescope
    """

    return pwiRequest(cmd="getsystem")

def getStatus():
    """
    Return a status object representing the tree structure of the XML text.
    Example: getStatus().mount.tracking --> "False"
    """

    return parseXml(getStatusXml())

### High-level command wrappers begin here ##############

### FOCUSER ###

def focuserConnect(port=1):
    """
    Connect to the focuser on the specified Nasmyth port (1 or 2).
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="connect")

def focuserDisconnect(port=1):
    """
    Disconnect from the focuser on the specified Nasmyth port (1 or 2).
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="disconnect")

def focuserMove(position, port=1):
    """
    Move the focuser to the specified position in microns
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="move", position=position)

def focuserIncrement(offset, port=1):
    """
    Offset the focuser by the specified amount, in microns
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="move", increment=offset)

def focuserStop(port=1):
    """
    Halt any motion on the focuser
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="stop")

def startAutoFocus():
    """
    Begin an AutoFocus sequence for the currently active focuser
    """

    return pwiRequestAndParse(device="focuser", cmd="startautofocus")

### ROTATOR ###

def rotatorMove(position, port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="move", position=position)

def rotatorIncrement(offset, port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="move", increment=offset)

def rotatorStop(port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="stop")

def rotatorStartDerotating(port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="derotatestart")

def rotatorStopDerotating(port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="derotatestop")

### MOUNT ###

def mountConnect():
    return pwiRequestAndParse(device="mount", cmd="connect")

def mountDisconnect():
    return pwiRequestAndParse(device="mount", cmd="disconnect")

def mountEnableMotors():
    return pwiRequestAndParse(device="mount", cmd="enable")

def mountDisableMotors():
    return pwiRequestAndParse(device="mount", cmd="disable")

def mountOffsetRaDec(deltaRaArcseconds, deltaDecArcseconds):
    return pwiRequestAndParse(device="mount", cmd="move", incrementra=deltaRaArcseconds, incrementdec=deltaDecArcseconds)

def mountOffsetAltAz(deltaAltArcseconds, deltaAzArcseconds):
    return pwiRequestAndParse(device="mount", cmd="move", incrementazm=deltaAzArcseconds, incrementalt=deltaAltArcseconds)

def mountGotoRaDecApparent(raAppHours, decAppDegs):
    """
    Begin slewing the telescope to a particular RA and Dec in Apparent (current
    epoch and equinox, topocentric) coordinates.

    raAppHours may be a number in decimal hours, or a string in "HH MM SS" format
    decAppDegs may be a number in decimal degrees, or a string in "DD MM SS" format
    """

    return pwiRequestAndParse(device="mount", cmd="move", ra=raAppHours, dec=decAppDegs)

def mountGotoRaDecJ2000(ra2000Hours, dec2000Degs):
    """
    Begin slewing the telescope to a particular J2000 RA and Dec.
    ra2000Hours may be a number in decimal hours, or a string in "HH MM SS" format
    dec2000Degs may be a number in decimal degrees, or a string in "DD MM SS" format
    """
    return pwiRequestAndParse(device="mount", cmd="move", ra2000=ra2000Hours, dec2000=dec2000Degs)

def mountGotoAltAz(altDegs, azmDegs):
    return pwiRequestAndParse(device="mount", cmd="move", alt=altDegs, azm=azmDegs)

def mountStop():
    return pwiRequestAndParse(device="mount", cmd="stop")

def mountTrackingOn():
    return pwiRequestAndParse(device="mount", cmd="trackingon")

def mountTrackingOff():
    return pwiRequestAndParse(device="mount", cmd="trackingoff")

def mountSetTracking(trackingOn):
    if trackingOn:
        mountTrackingOn()
    else:
        mountTrackingOff()

def mountSetTrackingRateOffsets(raArcsecPerSec, decArcsecPerSec):
    """
    Set the tracking rates of the mount, represented as offsets from normal
    sidereal tracking in arcseconds per second in RA and Dec.
    """
    return pwiRequestAndParse(device="mount", cmd="trackingrates", rarate=raArcsecPerSec, decrate=decArcsecPerSec)

def mountSetPointingModel(filename):
    return pwiRequestAndParse(device="mount", cmd="setmodel", filename=filename)

### M3 ###

def m3SelectPort(port):
    return pwiRequestAndParse(device="m3", cmd="select", port=port)

def m3Stop():
    return pwiRequestAndParse(device="m3", cmd="stop")



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



if __name__ == "__main__":
    main()
