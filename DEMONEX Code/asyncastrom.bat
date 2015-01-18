ssh2 -x jdeast@demonxl "cd /home/jdeast/idl/demonex/reductions; idl -e \"asyncsolve, '%1', %2, %3\""
REM ping 127.0.0.1 -n 30 -w 1000
