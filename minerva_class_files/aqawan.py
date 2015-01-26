#aqawan test module

import time, telnetlib, socket, threading

def aqawanCommunicate(message,lock):

	lock.acquire()
    messages = ['HEARTBEAT','STOP','OPEN_SHUTTERS','CLOSE_SHUTTERS',
                'CLOSE_SEQUENTIAL','OPEN_SHUTTER_1','CLOSE_SHUTTER_1',
                'OPEN_SHUTTER_2','CLOSE_SHUTTER_2','LIGHTS_ON','LIGHTS_OFF',
                'ENC_FANS_HI','ENC_FANS_MED','ENC_FANS_LOW','ENC_FANS_OFF',
                'PANEL_LED_GREEN','PANEL_LED_YELLOW','PANEL_LED_RED',
                'PANEL_LED_OFF','DOOR_LED_GREEN','DOOR_LED_YELLOW',
                'DOOR_LED_RED','DOOR_LED_OFF','SON_ALERT_ON',
                'SON_ALERT_OFF','LED_STEADY','LED_BLINK',
                'MCB_RESET_POLE_FANS','MCB_RESET_TAIL_FANS',
                'MCB_RESET_OTA_BLOWER','MCB_RESET_PANEL_FANS',
                'MCB_TRIP_POLE_FANS','MCB_TRIP_TAIL_FANS',
                'MCB_TRIP_PANEL_FANS','STATUS','GET_ERRORS','GET_FAULTS',
                'CLEAR_ERRORS','CLEAR_FAULTS','RESET_PAC']

    # not an allowed message
    if not message in messages:
       print 'Message not recognized: ' + message
       return -1

    IP = '192.168.1.10'
    port = 22004
    try:
        tn = telnetlib.Telnet(IP,port,1)
    except socket.timeout:
        print 'Timeout attempting to connect to the aqawan'
        return -1

    tn.write("vt100\r\n")
    tn.write(message + "\r\n")

    response = tn.read_until(b"/r/n/r/n#>",0.5)
    tn.close()
    return response

    return response.split("=")[1].split()[0]
    return tn.read_all()

    lock.release()

# should do this asychronously and continuously
def aqawan():

    while True:
        aqawanCommunicate('HEARTBEAT')
        time.sleep(15)
		
if __name__ == '__main__':

	lock = threading.lock()
    # run the aqawan heartbeat
    aqawanThread = threading.Thread(target=aqawan, args=())
    aqawanThread.start()
    while True:
		command = raw_input('enter Aqawan command: ')
		print aqawanCommunicate(command)