import imager, cdk700
import os, socket, time, subprocess, psutil
import ipdb

config_file = 'imager_t' + socket.gethostname()[1] + '.ini'
base_directory = 'C:\minerva-control'

for p in psutil.process_iter():
    try:
        if p.name() == 'MaxIm_DL.exe':
            try:
                camera = imager.imager(config_file,base_directory)
                # disconnect from the camera
                try: camera.disconnect_camera()
                except: pass
                try: subprocess.call(['Taskkill','/IM','MaxIm_DL.exe','/F'])
                except: pass
            except: pass

        elif p.name() == 'PWI.exe':
            telescope = cdk700.CDK700('telescope_' + socket.gethostname()[1] + '.ini', base_directory)

            # disconnect from mount
            try: telescope.shutdown()
            except: pass

            # kill PWI
            try: subprocess.call(['Taskkill','/IM','PWI.exe','/F'])
            except: pass
    except: pass

# reboot computer
os.system('shutdown -r -t 60')
