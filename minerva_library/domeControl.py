from filelock import FileLock
import control
import socket
import threading
import mail
import datetime, time
import sys, os
import utils

# check weather condition; close if bad, open and send heartbeat if good; update dome status
def domeControl(minerva,number,day=False):

    minerva.logger.info("Starting domeControl")
    dome = minerva.domes[number-1]
    lastnight = ''
    while True:
        t0 = datetime.datetime.utcnow()

        # roll over the logs to a new day
        thisnight = datetime.datetime.strftime(t0,'n%Y%m%d')
        if thisnight != lastnight:
            minerva.update_logpaths(minerva.base_directory + '/log/' + thisnight)
            lastnight = thisnight

        # see if the dome was requested to be open
        openRequested = os.path.isfile(minerva.base_directory + '/minerva_library/aqawan' + str(number) + '.request.txt')
        day = os.path.isfile(minerva.base_directory + '/minerva_library/sunOverride.txt')

        if not minerva.site.oktoopen(domeopen=dome.isOpen()):
            if minerva.site.oktoopen(domeopen=dome.isOpen(),ignoreSun=True):
                minerva.logger.info('Weather not ok to open; resetting timeout')
                minerva.site.lastClose = datetime.datetime.utcnow()
                dome.close_both()
        elif (datetime.datetime.utcnow() - minerva.site.lastClose).total_seconds() < (30.0*60.0):
            minerva.logger.info('Conditions must be favorable for 30 minutes before opening; last bad weather at ' + str(minerva.site.lastClose))
            dome.close_both() # should already be closed, but for good measure...
        elif not openRequested:
            minerva.logger.info("Weather is ok, but domes are not requested to be open")
            dome.close_both()
        else:
            minerva.logger.debug('Weather is good; opening dome')

            kwargs={'day' : day, 'num' : number}
            openthread = threading.Thread(target=minerva.dome_open,kwargs=kwargs)
            openthread.name = "A" + str(number) + '_OPEN'
            openthread.start()
            
            # only send heartbeats when we want it open
            dome.heartbeat()

        status = dome.status()
        isOpen = (status['Shutter1'] == 'OPEN') and (status['Shutter2'] == 'OPEN')
        
        filename = minerva.base_directory + '/minerva_library/aqawan' + str(number) + '.stat'
        with FileLock(filename):
            with open(filename,'w') as fh:
                fh.write(str(datetime.datetime.utcnow()) + ' ' + str(isOpen))

        # check for E-stops
        response = dome.send('CLEAR_FAULTS')
        if 'Estop' in response:
            if not dome.estopmailsent:
                mail.send("Aqawan " + str(number) + " Estop has been pressed!",dome.estopmail,level='serious')
                dome.estopmailsent = True
            else:
                dome.estopmailsent = False

        # ensure 4 hearbeats before timeout 
        sleeptime = max(14.0-(datetime.datetime.utcnow() - t0).total_seconds(),0)
        time.sleep(sleeptime)

    dome.close_both()

def domeControl_catch(minerva, number, day=False):
    try:
        domeControl(minerva, number, day=day)
    except Exception as e:
        minerva.domes[number-1].logger.exception('DomeControl thread died: ' + str(e.message) )
        body = "Dear benevolent humans,\n\n" + \
            "I have encountered an unhandled exception which has killed the "+\
            "dome control thread. The error message is:\n\n" + \
            str(e.message) + "\n\n" + \
            "Check control.log for additional information. Please "+\
            "investigate, consider adding additional error handling, and "+\
            "restart 'domeControl.py'. The heartbeat *should* close the domes, "+\
            "but if it is in MANUAL or DISABLE mode, or if the motors have "+\
            "been overloaded or an E-stop has been pressed, it will not close. "+\
            "Please investigate immediately.\n\n" + \
            "Love,\n" + \
            "MINERVA"
        mail.send("DomeControl thread died",body,level='critical')
        sys.exit()

def domeControlThread(minerva,day=False):
    threads = []
    for dome in [1,2]:
        minerva.logger.info("Starting dome control thread for Aqawan " + str(dome))
        thread = threading.Thread(target = domeControl_catch,args=(minerva,dome,)) 
        thread.name = 'A' + str(dome)
        threads.append(thread)

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()        

if __name__ == '__main__':

    # python bug work around -- strptime not thread safe. Must call this once before starting threads                              
    junk = datetime.datetime.strptime('2000-01-01 00:00:00','%Y-%m-%d %H:%M:%S')

    base_directory = '/home/minerva/minerva-control'
    if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
    minerva = control.control('control.ini',base_directory)
    domeControlThread(minerva)
