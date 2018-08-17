#P25USB photodetector modules uses an active x control driver
#might need to generate a wrapper with win32com module
import win32com.client

class exposure_meter:
	
	def __init__(self):
		
		#TODO: connect to activex driver with win32com and save it to self.object
		#http://stackoverflow.com/questions/1065844/what-can-you-do-with-com-activex-in-python 
		#has a detailed description of how to generate wrapper with win32com
		
		#initialize object
		self.connect()
		self.object.Continuous = False		#sets non-continuous mode ie fixed number readings
		self.object.Triggered = False 		#disable external trigger input.
		self.object.OutputSignal = False 	#sets the user output (violet wire) to 0 volts.
		self.object.OutputVoltage = True 	#turns on the photomultiplier HV supply.
		self.object.Period = 100 			#sets gate period to one second.
		self.object.ReadingCount = 100 		#sets number of readings to be taken as 100
		
	def connect(self):
		self.object.Open(1)
		
	def release(self):
		self.object.OutputVoltage = False	#turns off the photomultiplier HV supply.
		self.object.Close()
		
	#start counting
	def start(self):
		self.object.Start()
	
	#stop counting
	def stop(self):
		self.object.Stop()