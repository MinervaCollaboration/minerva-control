import com, ipdb
#S Define exposure meter class
class expmeter:

    #S Initialize with com
    def __init__(self, config=None, base=None):
        self.com = com.com(id,night,configfile=configfile)
    #? Want this to be able to read value of exposure meter? Should this be
    #? a com.send to send request for value? Look into docs for P25USB.
    def read(self):
        pass
    #S Logging stuff.
    #TODO Read later.
    def startLogging(self):
        ipdb.set_trace()
        self.com.send('R' + chr(1))
        self.com.send('P' + chr(100))
        self.com.send('D')

        measurementspersec = 2.0
        
        self.com.send('P' + chr(int(100.0/measurementspersec)))

        self.com.open()
        self.com.ser.write('C' + self.com.termstr)
        while True:
            try:
                while self.ser.inWaiting() < 4:
                    time.sleep(0.01)
                self.com.logger.info(str(datetime.datetime.utcnow()), struct.unpack('I',self.ser.read(4))[0])
            except:  
                break
            
        self.com.ser.write("\r") # stop measurements
        self.com.ser.write('V'+ chr(0) + chr(0) + self.termstr) # turn off voltage
        self.com.close() # close connection
        ipdb.set_trace()

if __name__ == "__main__":
        
    expmeter = expmeter(config='expmeter.ini',base="C:/minerva-control/")
    expmeter.startLogging()

    ipdb.set_trace()

    expmeter.com.send('R' + chr(1))
    expmeter.com.send('P' + chr(100))
    expmeter.com.send('D')

    measurementspersec = 2.0
    
    expmeter.com.send('P' + chr(int(100.0/measurementspersec)))

    expmeter.com.open()
    expmeter.com.ser.write('C' + expmeter.com.termstr)
    while True:
        try:
            while expmeter.ser.inWaiting() < 4:
                time.sleep(0.01)
            print str(datetime.datetime.utcnow()), struct.unpack('I',expmeter.ser.read(4))[0]
        except:  
            break
        
    expmeter.com.ser.write("\r") # stop measurements
    expmeter.com.ser.write('V'+ chr(0) + chr(0) + expmeter.termstr) # turn off voltage
    expmeter.com.close() # close connection
    ipdb.set_trace()
