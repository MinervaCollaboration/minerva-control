import imager, cdk700
import os, socket, time, subprocess
import ipdb

config_file = 'imager_t' + socket.gethostname()[1] + '.ini'
base_directory = 'C:\minerva-control'

try: camera = imager.imager(config_file,base_directory)
except: pass

# disconnect from the camera
try: camera.disconnect_camera()
except: pass

try: subprocess.call(['Taskkill','/IM','MaxIm_DL.exe','/F'])
except: pass

# disconnect from rotator
telescope = cdk700.CDK700('telescope_' + socket.gethostname()[1] + '.ini', base_directory)

# disconnect from mount
try: telescope.shutdown()
except: pass

# kill PWI
try: telescope.killPWI()
except: pass

# reboot computer
os.system('shutdown -r -t 60')
