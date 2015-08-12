from minerva_library import spectrograph
import ipdb
import socket
import time

ipdb.set_trace()
base_directory = '/home/minerva/minerva_control'
if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
test_spec = spectrograph.spectrograph('spectrograph.ini',base_directory)
test_spec.connect_server()
test_spec.cell_heater_on()
test_spec.cell_heater_temp()
test_spec.cell_heater_get_set_temp()
test_spec.cell_heater_set_temp(55)
test_spec.cell_heater_off()
