from minerva_library import spectrograph_server

"""main routine running on Spectrograph computer, 
sets up a TCP/IP server and listen for incoming command"""

if __name__ == '__main__':
	
	base_directory = 'C:\minerva-control'
	new_spectrograph_server = spectrograph_server.server('S1', base_directory)
	new_spectrograph_server.run_server()
