


if __name__ == "__main__":

	import sys
	import time
	import os
	import socket

	from si.client import SIClient
	from si.imager import Imager

   
	host = "localhost"
	port = 2055
	client = SIClient (host, port)

	imager = Imager (client)
	imager.nexp = 1							# number of exposures
	imager.texp = 1.0						# exposure time, float number
	imager.nome = "image"					# file name to be saved
	imager.dark = False						# dark frame?
	imager.frametransfer = False			# frame transfer?
	imager.getpars = False					# Get camera parameters and print on the screen
	#t0 = time.time ()

	try:

		ret = ""
		shutter = ""
		if imager.dark:
			shutter = "closed"
		else:
			shutter = "opened"

		frametransfer = ""
		if imager.frametransfer:
			frametransfer = "with"
		else:
			frametransfer = "without"

			
		print "Taking %d image(s) of %f seconds each and saving to '%s' with the shutter %s ... (%s frame transfer)" % (imager.nexp,
																														imager.texp,
																														imager.nome,
																														shutter,
																														frametransfer),
		ret = imager.do ()
		
	except socket.error, e:
		print "Socket error: %s" % e
		print "ERROR"
		sys.exit (1)

	if ret:
		print "DONE"
	else:
		print "INTERRUPTED"
	  
