import ipdb
from ctypes import *
import sys
# Load DLL into memory.

mydll = windll.LoadLibrary("C:\minerva-control\minerva_library\TC200x.dll")

#p = 0
#i= 0
#d =0
#print mydll.TC200x_getPID(p,i,d)

temp = c_double(0.0)

#ViStatus _VI_FUNC  TC200x_init (ViRsrc resourceName, int baudRate, ViBoolean IDQuery, ViBoolean resetDevice, ViSession *vi);
vi = 0
resourceManagerHandle = c_int(0)
baudrate = c_int(19200)
port = c_char_p('COM3')
idquery = c_bool(False)
resetdevice = c_bool(False)
#http://www.ni.com/white-paper/8911/en/
print mydll.TC200x_init(port,baudrate,idquery,resetdevice,byref(resourceManagerHandle))


#ViStatus _VI_FUNC TC200x_get_ambient_temperature (ViSession vi, double *ambientTemperature);
mydll.TC200x_get_ambient_temperature(vi,byref(temp))
print temp.value

#sys.exit()

ipdb.set_trace()


dll = ctypes.WinDLL ("C:\minerva-control\minerva_library\TC200x.dll")


# Set up prototype and parameters for the desired function call.
# HLLAPI

hllApiProto = ctypes.WINFUNCTYPE (ctypes.c_int,ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
hllApiParams = (1, "p1", 0), (1, "p2", 0), (1, "p3",0), (1, "p4",0),

# Actually map the call ("HLLAPI(...)") to a Python name.

hllApi = hllApiProto (("HLLAPI", hllDll), hllApiParams)

# This is how you can actually call the DLL function.
# Set up the variables and call the Python name with them.

p1 = ctypes.c_int (1)
p2 = ctypes.c_char_p (sessionVar)
p3 = ctypes.c_int (1)
p4 = ctypes.c_int (0)
hllApi (ctypes.byref (p1), p2, ctypes.byref (p3), ctypes.byref (p4))
