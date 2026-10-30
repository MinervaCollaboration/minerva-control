# windows 7 os.mkdir started (on 4/1/2023) to make them read only folders and I'm not sure how to programmatically give them write access. Create a bunch and manaully remove the read-only flag on windows
import datetime
import os

for i in range(1000):
    date = datetime.datetime.utcnow() + datetime.timedelta(days=i)
    night = 'n' + date.strftime('%Y%m%d')
    print night

    subdir = "/Data/kiwispec/" + night
    if not os.path.exists(subdir): os.mkdir(subdir)

    subdir = "/Data/kiwilog/" + night
    if not os.path.exists(subdir): os.mkdir(subdir)
