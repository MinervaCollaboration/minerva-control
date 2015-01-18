MODE COM2: BAUD=96 PARITY=N DATA=8 STOP=1
copy poweroff.txt com2
PING 127.0.0.1 -n 31
copy poweron.txt com2