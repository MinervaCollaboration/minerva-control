import subprocess, os, socket, time
import minerva_class_files.mail as mail

hostname = socket.gethostname()

if os.path.exists("running.txt"):
    mail.send(hostname + " rebooted during observations","Restarting observations")
    subprocess.call(['python','main.py'],shell=True)
else:
    mail.send(hostname + " rebooted", "")

time.sleep(60)
