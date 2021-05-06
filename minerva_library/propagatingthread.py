from threading import Thread

class PropagatingThread(Thread):
#    def __init__(self):
#        super().__init__()

    def run(self):
        self.exc = None
#        self.ret = None
        try:
            if hasattr(self, '_Thread__target'):
                # Thread uses name mangling prior to Python 3.
                self.ret = self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
            else:
                self.ret = self._target(*self._args, **self._kwargs)
        except BaseException as e:
            self.exc = e

    def join(self, timeout=None):
#        super().join(timeout)
        super(PropagatingThread, self).join(timeout)
        if self.exc:
            raise self.exc
#        return self.ret # Join doesn't return anything; this shouldn't either
