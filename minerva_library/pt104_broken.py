#tc-08.py 
import ctypes as ct 

## Interface with the dll 
tc08 = ct.windll.LoadLibrary('tc0832') 

## set_channel() 
tc08_set_channel = tc08.tc08_set_channel 
tc08_set_channel.restype = ct.c_short 
tc08_set_channel.argtypes = (ct.c_ushort, ct.c_ushort, ct.c_char, ct.c_ushort, ct.c_short, ct.c_short) 

def do_tc08_set_channel(port=1, channel=1, tc_type='K', filter_factor=10, offset=0, slope=0): 
return tc08_set_channel(port, channel, ct.c_char(tc_type), filter_factor, offset, slope) 

## get_temp() 
tc08_get_temp = tc08.tc08_get_temp 
tc08_get_temp.restype = ct.c_short 
tc08_get_temp.argtypes = (ct.POINTER(ct.c_long), ct.c_ushort, ct.c_ushort, ct.c_short) 
## argtypes are for (temp (pointer), port, channel, filtered) 

## get_cold_junction() 
tc08_get_cold_junction = tc08.tc08_get_cold_junction 
tc08_get_cold_junction.restype = ct.c_short 
tc08_get_cold_junction.argtypes = (ct.POINTER(ct.c_long), ct.c_short) 


## End type setup ---------------------------------------------------------------------# 

## Open the device 
print "Device open:", tc08.tc08_open_unit(1) 

## Set up the happy channel we want to use (6 in this case) 
channel = 6 
print "Channel:", str(channel), "status:", do_tc08_set_channel(1,6,'K',10,0,0) 


## So far so good.. now to get a temperature 
temp = ct.c_long() 
print "get_temp returns:", tc08_get_temp(temp,1,6,0) 
print "Temperature:", temp.value 

## What about the cold junction? 
coldtemp = ct.c_long() 
print "get_cold_junction returns:", tc08_get_cold_junction(coldtemp,1) 
print "Cold junction Temperature:", coldtemp.value 


## Close the device 
tc08.tc08_close_unit(2) 

# End 
