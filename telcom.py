import threading
from minerva_library import telcom_server
from minerva_library import imager_server
import socket

"""main routine running on Telescope computer, 
sets up instrument servers and listen for incoming command"""

if __name__ == '__main__':
        
	base_directory = 'C:\minerva-control'
	if socket.gethostname() == 'Minervared2-PC':
                image_server_config_file = 'imager_server_red.ini'
        else:
                image_server_config_file = 'imager_server.ini'
	
	telcom_server = telcom_server.server('telcom_server.ini',base_directory)
	threading.Thread(target = telcom_server.run_server).start()
	
	imager_server = imager_server.server(image_server_config_file,base_directory)
	imager_server.run_server()

	
