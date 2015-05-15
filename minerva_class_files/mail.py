import smtplib, json, datetime, random
import ipdb
from email.mime.text import MIMEText

def send(subject,body,level='normal',attachment=None):
    
    # read in the contacts directory (proprietary)
    with open('directory.txt') as dirfile:
        directory = json.load(dirfile)

    # filter recipients according to alert level, preferences
    hournow = datetime.datetime.utcnow().hour
    recipients = []
    for contact in directory:
        if level in contact['levels']:
            if hournow <= contact['forbiddenwindow'][0] or hournow >= contact['forbiddenwindow'][1]:
                if random.random() < contact['probability']:
                    recipients.append(contact['email'])

    # login credentials (proprietary)
    f = open('emaillogin.txt')
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
