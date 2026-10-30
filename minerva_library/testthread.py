from propagatingthread import PropagatingThread
from threading import Thread
import time

def f(*args, **kwargs):
    print(args)
    print(kwargs)
    print test
    print "testing f"
#    raise Exception('I suck at this')

#t = PropagatingThread(target=f, args=(5,), kwargs={'hello':'world'})
t = Thread(target=f, args=(5,), kwargs={'hello':'world'})
t.start()
t.join()

print "testing"
time.sleep(10)
print "testing2"
