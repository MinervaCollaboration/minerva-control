import com, ipdb

class vacuumgauge:
    def __init__(self, id, night, configfile='minerva_class_files/com.ini'):
        self.com = com.com(id,night,configfile=configfile)

    def pressure(self):
        return self.com.send('RD')

if __name__ == "__main__":

    specgauge = vacuumgauge('specgauge','n20150521')
    print specgauge.pressure()
    ipdb.set_trace()
