#!/bin/bash

# Define the path where our text file will be placed
path="read_temps/stability_txts/"

# First, let's pull yesterday's date
yesterday=`date -d "yesterday 13:00" '+%Y-%m-%d'`
echo $yesterday
# Next, extract the day, month, and year from `$yesterday`
day="${yesterday:8:2}"
month="${yesterday:5:2}"
year="${yesterday::4}"

# The path + file names take the following form
fname=192.168.1.51/usr-cgi/da_loglist.cgi?dir=2019_${month}\/\$file=${day}.csv

# We can `wget` our files using the above path
wget --continue $fname

# This is what the .csv file is called
csv_fname=da_loglist.cgi?dir=2019_${month}%2F\$file=${day}.csv

# HEre is the handy YYYYMMDD.txt file name we will assign to our new csv->txt file
txt_fname=2019${month}${day}.txt

# Now convert our .csv file into a more convenient .txt file
mv $csv_fname "$path$txt_fname"
