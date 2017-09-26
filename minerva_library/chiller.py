import serial
from astropy.time import Time
import datetime
import time

filenamepre = str("Oasis3temp2457899")

#creating a file where the data will be saved.

filename= filenamepre+".txt" 

with open(filename, 'a') as f:

    ser= serial.Serial(10, baudrate = 9600, bytesize = serial.EIGHTBITS, parity = serial.PARITY_NONE, stopbits= serial.STOPBITS_ONE, timeout = 1.5)
    ser.flushInput()
    ser.flushOutput()
    ser.write("TEMP?") 
    ser.write("\r\n")
    temp=ser.read(10)
    ser.write("SETTEMP?") 
    ser.write("\r\n")
    setpoint=ser.read(10)
    setpoint2=setpoint[0:10]
    ser.write("PUMPTEMP?")  
    ser.write("\r\n")
    pumptemp=ser.read(10)
    currenttime = datetime.datetime.now()
    JDtime = Time(str(currenttime), format='iso', scale = 'utc')
    JD =str(JDtime.jd)
    ser.close()
    f.write(temp+" "+setpoint2+" "+pumptemp+" "+JD)
    f.write("\n")
    f.close
