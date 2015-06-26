import threading
from minerva_library import telcom_server
from minerva_library import imager_server

"""main routine running on Telescope computer, 
sets up instrument servers and listen for incoming command"""

if __name__ == '__main__':

	base_directory = 'C:\minerva-control'
	
	telcom_server = telcom_server.server('telcom_server.ini',base_directory)
	threading.Thread(target = telcom_server.run_server).start()
	
	imager_server = imager_server.server('imager_server.ini',base_directory)
	imager_server.run_server()

	
