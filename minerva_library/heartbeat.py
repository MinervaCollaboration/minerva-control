import psutil, os
import ipdb


bad = True
for pid in psutil.pids():
    p = psutil.Process(pid)
    if p.name() == "python":
        if len(p.cmdline()) == 3:
            if (p.cmdline())[2] == '--red'  and (p.cmdline())[1] == 'domeControl.py':
                print pid, p.username(), p.cmdline()
                bad = False

if bad:
   os.system('python domeControl.py --red') 
