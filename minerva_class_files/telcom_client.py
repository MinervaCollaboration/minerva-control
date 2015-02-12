# prototype telcom client module
import threading, socket, time

ip_address = ['localhost']
port = 50007

#To Do: add logger, add higher level methods with easy instrument control
class client:
	#initialize client class with IP list and port, start up communication threads
	def __init__(self,IP=ip_address,PORT=port):
		self.lock = threading.Lock()
		self.ip = IP
		self.port = PORT
		self.t_thread = list()
		self.s = list()
		for i in range(len(self.ip)):
			self.s.append(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
			self.t_thread.append(threading.Thread(target = self.send,args = ('hello',i)))
			self.t_thread[i].start()
	#allocate a new socket object, no threading
	def connect(self,telcom):
		while True:
			try:
				self.s[telcom].connect((self.ip[telcom], self.port))
				break
			except:
				print "connection cannot be made, reconnecting in 10 seconds"
				time.sleep(10)
				self.s[telcom] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	#send msg to telcom index number in ip_address, no threading
	def send(self,msg,telcom):
		try:
			self.s[telcom].sendall(msg)
		except:
			print "connection lost, reconnecting"
			self.connect(telcom)
			self.s[telcom].sendall(msg)
	#send msg to all telcom in ip_address by starting new threads for each connection
	def send_all(self,msg):
		for i in range(len(self.t_thread)):
			if self.t_thread[i].is_alive() == False:
				self.t_thread[i] = threading.Thread(target = self.send,args = (msg,i))
				self.t_thread[i].start()


#test program
if __name__ == '__main__':

	telcom = client()
	while True:
		message = raw_input('enter message to send: ')
		telcom.send_all(message)