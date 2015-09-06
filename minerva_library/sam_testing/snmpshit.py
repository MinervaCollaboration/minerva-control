from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.proto.rfc1902 import Integer, IpAddress

import ipdb
ipdb.set_trace()
ip = '192.168.10.91'
community = 'public'
value = (1,3,6,1,4,1,17420,1,2,9,1,13,0)

generator = cmdgen.CommandGenerator()
comm_data = cmdgen.CommunityData('server', community,1)
#S I think we want this on port 80, not 161
transport = cmdgen.UdpTransportTarget((ip,80))
real_fun = getattr(generator,'nextCmd')
res = (errorIndication,errorStatus,errorIndex,varBinds)=real_fun(comm_data,transport,value)

end='end'
