from PyAPT import APTMotor
import datetime
import time
import ipdb
#S Focus stage
#SN = 80851661
#HWTYPE = 31
ipdb.set_trace()
#S Iodine stage
SN = 40864672
HWTYPE = 12

motor = APTMotor(SN,HWTYPE)
start = datetime.datetime.now()
motor.initializeHardwareDevice()
end = datetime.datetime.now()
print 'connected :' + str((end-start).total_seconds())

currentPos = motor.getPos()

print currentPos

motor.mAbs(0.0)

#time.sleep(5)

currentPos = motor.getPos()

print currentPos


start = datetime.datetime.now()
motor.cleanUpAPT()
end = datetime.datetime.now()
print 'connected :' + str((end-start).total_seconds())



