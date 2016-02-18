# this file contains a set of generally useful utility functions for MINERVA operations
import re

# converts a sexigesimal string to a float
# the string may be delimited by either spaces or colons
def ten(string):
    array = re.split(' |:',string)
    if "-" in array[0]:
        return float(array[0]) - float(array[1])/60.0 - float(array[2])/3600.0
    return float(array[0]) + float(array[1])/60.0 + float(array[2])/3600.0

