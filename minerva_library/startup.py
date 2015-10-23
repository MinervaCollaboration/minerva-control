import subprocess, os, socket, time
import mail
import datetime

hostname = socket.gethostname()

body = "Dear benevolent humans,\n\n" + \
       "If someone did not intentionally reboot me, I require your assistance to recover from a recent power outage. Please:\n\n" + \
       "1) Make sure the telescope is connected, the drives are enabled, and the tracking is off.\n" + \
       "2) Home the telescope\n" + \
       "   * If this fails, you may need to power cycle the 'T# panel' and start over:\n" + \
       "   * T1 - 192.168.1.36\n" + \
       "   * T2 - 192.168.1.37\n" + \
       "   * T3 - 192.168.1.38\n" + \
       "   * T4 - 192.168.1.39\n" + \
       "3) Make sure the rotator is connected and the 'Alt Az Derotate' is off.\n" + \
       "4) Home the rotator\n" + \
       "5) Check the rotator zero points (PWI rotate tab)\n" + \
       "   * T1 - 56.42\n" + \
       "   * T2 - 182.70\n" + \
       "   * T3 - 198.75\n" + \
       "   * T4 - 224.18\n" + \
       "   If those aren't the same, don't change them, but note it, and don't be surprised if you get an email after the first science image that the rotator is screwed up.\n" + \
       "6) Home the focuser\n" + \
       "Love,\n" + \
       "MINERVA"

body2 = "Dear benevolent humans,\n\n" + \
       "I have successfully completed my daily reboot. No action is required.\n\n" + \
       "Love,\n" + \
       "MINERVA"

now = datetime.datetime.now()

# if it's between 3:30 and 3:45, it's part of the normal daily reboot
timediff = (now - datetime.datetime(now.year, now.month,now.day,15,30)).total_seconds()
if timediff > 0 and timediff < 900:
    mail.send(hostname + " finished daily reboot",body2,level="normal")
else:
    # otherwise, there was probably a power outage
    mail.send(hostname + " rebooted unexpectedly and requires assistance",body,level="serious")

time.sleep(60)
