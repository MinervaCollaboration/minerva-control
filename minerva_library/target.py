import numpy as np
import ipdb

class target:
    def __init__(self,target_dict):
        #S this takes the target_dicttionary input and iterates over it,
        #S assiging it an appropriate attibute to the class.
        for key, value in target_dict.iteritems():
            setattr(self,key,value)
    def test(self):
        print 'test'


if __name__ == '__main__':
    z= {'a':1,'b':2,'c':[1,2,34,4,54]}
    test=target(z)
    ipdb.set_trace()

