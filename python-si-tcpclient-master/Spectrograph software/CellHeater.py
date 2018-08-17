import com, ipdb

class CellHeater:

    def __init__(self, id, night, configfile='minerva_class_files/com.ini'):
        self.com = com.com(id,night,configfile=configfile)

    file = open('heatertemps.txt', 'w')
    print >> file, "TEMP SET", "TEMP ACTUAL"

    def getTemp(self):
        return self.com.send('temps?')
        
    def setTemp(self, temp):
        return self.com.send('tset' + str(temp))

    def write(self):
        print >> file, self.com.send(self.getTemp())
        

if __name__ == "__main__":
    heater = CellHeater('I2Heater','n20150521')
    print heater.getTemp()
    ipdb.set_trace()
        
