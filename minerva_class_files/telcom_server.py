# prototype for telcom server module
# right now only prints received data to console
import socket

HOST = ''                 # Symbolic name meaning all available interfaces
PORT = 50007              # Arbitrary non-privileged port

while 1:
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.bind((HOST, PORT))
	s.listen(1)
	conn, addr = s.accept()
	print 'Connected by', addr
	while 1:
		try:
			data = conn.recv(1024)
			if not data:
				print 'no data received'
				break
			print 'Received', repr(data)
		except:
			print 'Connection lost'
			break
	s.close()
