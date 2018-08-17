import serial
import time

data = []
def opendome():
    ser = serial.Serial(1, baudrate=9600, bytesize = serial.EIGHTBITS)
    count = 0
    while (count <20):
        ser.write('a')
        time.sleep(0.6)
        count = count +1
        #print count
    while (19 <count <40):
        ser.write('b')
        time.sleep(0.6)
        count = count +1
        #print count 
    ser.close()
    
def openshutter1():
    ser = serial.Serial(1, baudrate=9600, bytesize = serial.EIGHTBITS)
    count = 0
    while (count <20):
        ser.write('a')
        time.sleep(0.6)
        count = count +1
        #print count
    ser.close()
def openshutter2():
    ser = serial.Serial(1, baudrate=9600, bytesize = serial.EIGHTBITS)
    count = 0
    while (count <20):
        ser.write('b')
        time.sleep(0.6)
        count = count +1
        #print count
    ser.close()
    
def closedome():
    ser = serial.Serial(1, baudrate=9600, bytesize = serial.EIGHTBITS)
    count = 0 
    while (count <20):
        ser.write('A')
        time.sleep(0.6)
        count = count +1
        #print count
    while (19<count <40):
        ser.write('B')
        time.sleep(0.6)
        count = count +1
        #print count
    ser.close()
    
def closeshutter1():
    ser = serial.Serial(1, baudrate=9600, bytesize = serial.EIGHTBITS)
    count = 0 
    while (count <20):
        ser.write('A')
        time.sleep(0.6)
        count = count +1
        #print count
    ser.close()
    
def nudgeshutter1open():
    ser = serial.Serial(1, baudrate=9600, bytesize = serial.EIGHTBITS)
    ser.write('a')
    ser.close()
def nudgeshutter2open():
    ser = serial.Serial(1, baudrate=9600, bytesize = serial.EIGHTBITS)
    ser.write('b')
    ser.close()
def nudgeshutter1closed():
    ser = serial.Serial(1, baudrate=9600, bytesize = serial.EIGHTBITS)
    ser.write('A')
    ser.close()
def nudgeshutter2closed():
    ser = serial.Serial(1, baudrate=9600, bytesize = serial.EIGHTBITS)
    ser.write('B')
    ser.close()

def closeshutter2():
    ser = serial.Serial(1, baudrate=9600, bytesize = serial.EIGHTBITS)
    count = 0 
    while (count <20):
        ser.write('B')
        time.sleep(0.6)
        count = count +1
        print count
    ser.close()
    
def dometemp():
    ser = serial.Serial(2, baudrate = 9600)
    hexcode = "\x49"
    ser.write(hexcode)
    out = ser.read(size = 91)
    print out
    
def isdomeclosed():
    ser = serial.Serial(17, baudrate = 9600)
    hexcode = "\x49"
    ser.write(hexcode)
    out = ser.read(size =50)
    print out
    