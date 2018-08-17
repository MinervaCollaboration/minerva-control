from configobj import ConfigObj
import time, sys, socket, logging, datetime, ipdb, time, json




class PT100:

    def __init__(self, config, base):

        self.config_file = config
		self.base_directory = base
		self.load_config()
		self.setup_logger()

	def load_config(self):
	
		try:
			config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.ip = config['Setup']['IP']
			self.port = int(config['Setup']['PORT'])
			self.logger_name = config['Setup']['LOGGER_NAME']
			self.description = config['Setup']['DESCRIPTION']
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()

	#set up logger object
	def setup_logger(self,night='dump'):
		
		self.logger = logging.getLogger(self.logger_name)
		formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
		log_path = self.base_directory + '/log/' + night
		if os.path.exists(log_path) == False:
			os.mkdir(log_path)
		fileHandler = logging.FileHandler(log_path + '/' + self.logger_name +'.log', mode='a')
		fileHandler.setFormatter(formatter)
		streamHandler = logging.StreamHandler()
		streamHandler.setFormatter(formatter)

		#clear handlers before setting new ones
		self.logger.handlers = []
		
		self.logger.setLevel(logging.DEBUG)
		self.logger.addHandler(fileHandler)
		self.logger.addHandler(streamHandler)
		
		
    def createSocket(self);
        #!/usr/bin/env python

        # server listens on a specified port, prints out msg, and sends an # acknowledgment.

        port = 6129

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        s.bind(("",self.port))

        print "Waiting on port ",port

        while 1 : data, addr = s.recvfrom(1024) print "socketprac.py received:",data print "addr was ",addr time.sleep(1.0) s.sendto("Got it.",addr);


        #!/usr/bin/env python

        # client sends a message and waits for a reply

        ds = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        ds.sendto("Hello there!",(self.ip,self.port))

        data, addr = ds.recvfrom(1024)

        print "reply received:",data," from ",addr


    """
    def connect(self):
         self.sock.connect((self.ip, self.port))

    def send(self, msg):
        totalsent = 0
        while totalsent < MSGLEN:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent

    def receive(self):
        chunks = []
        bytes_recd = 0
        while bytes_recd < MSGLEN:
            chunk = self.sock.recv(min(MSGLEN - bytes_recd, 2048))
            if chunk == '':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
        return ''.join(chunks) """
        
if __name__ == "__main__":
    p3 = PT100('P3', 'n20150522', configfile = 'PT100.ini')
    p3.connect()
    ipdb.set_trace()