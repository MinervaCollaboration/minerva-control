import com, ipdb

class atmosGauge:

    def __init__(self, id, night, configfile='minerva_class_files/com.ini'):
        self.com = com.com(id,night,configfile=configfile)

    def open(self):
	self.com.send('OPEN')
	
    def close(self):
	self.com.send('CLOSE')	

    def receive(self):
	self.com.send('R')
			
if __name__ == "__main__":
    gauge = atmosGauge('atmosGauge','n20150521')
    gauge.open()
    gauge.receive()

