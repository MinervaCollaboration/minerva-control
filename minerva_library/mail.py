import smtplib
import json
import datetime
import random
import ipdb
import sys
import socket
from email.mime.text import MIMEText
sys.dont_write_bytecode = True


def send(subject,body,level='normal',attachment=None):
#	return
	host = socket.gethostname()
	if host == 'Main':
        	credential_directory = '/home/minerva/minerva-control/credentials/'
        else:
                credential_directory = 'C:/minerva-control/credentials/'
	# read in the contacts directory (proprietary)
	with open(credential_directory + 'directory.txt') as dirfile:
		directory = json.load(dirfile)

	# filter recipients according to alert level, preferences
	hournow = datetime.datetime.utcnow().hour
	recipients = []
	for contact in directory:
		if level in contact['levels']:
			if hournow <= contact['forbiddenwindow'][0] or hournow >= contact['forbiddenwindow'][1]:
				if random.random() < contact['probability']:
					recipients.append(contact['email'])

	if len(recipients) == 0: return

	# login credentials (proprietary)
	f = open(credential_directory + 'emaillogin.txt')
	username = f.readline()
	password = f.readline()
	f.close()

	# Prep email
	msg = MIMEText(body)
	msg['From'] = username.strip()
	msg['To'] = ', '.join(recipients)
	msg['Subject'] = subject
# attachments don't work like this!  
#    if attachment <> None: msg.attach(MIMEText(file(attachment).read()))   

	# send email
	server = smtplib.SMTP('smtp.gmail.com')
	server.starttls()
	server.login(username,password)
	server.sendmail(username, recipients, msg.as_string())
	server.quit()

if __name__ == "__main__":
	send('test subject','body of email')
	
