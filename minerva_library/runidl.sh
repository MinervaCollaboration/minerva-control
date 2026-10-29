#! /bin/bash

echo $SHELL
echo "this is the argument"
echo "$1"
echo "that was the argument"
IDL_PATH="<IDL_DEFAULT>:+/home/minerva/idl/" export IDL_PATH
echo $IDL_PATH

#source /home/minerva/.bashrc
echo $1
echo "plotallexp, '"$1"'"
/usr/local/bin/idl -e "plotallexp, '"$1"'"