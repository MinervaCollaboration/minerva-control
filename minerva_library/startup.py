import subprocess, os, socket, time
import mail

hostname = socket.gethostname()

body = "Dear benevolent humans,\n\n" + \
       "I require your assistance to recover from a recent power outage. Please:\n\n" + \
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
       "6) Start an autofocus sequence, wait 30 seconds, and cancel it (if you don't do this, the scripted autofocus will use the default values which don't span enough range).\n\n" + \
       "Love,\n" + \
       "MINERVA"

mail.send(hostname + " rebooted during observations",body,level="serious")

time.sleep(60)
