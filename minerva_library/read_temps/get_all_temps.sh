#!/bin/bash

path="stability_txts/"

yesterday=`date -d "yesterday 13:00" '+%Y-%m-%d'`
day="${yesterday:8:2}"
month="${yesterday:5:2}"
year="${yesterday::4}"

for month in {01..9}
do 
	for day in {01..31}
	do	
                fname=192.168.1.51/usr-cgi/da_loglist.cgi?dir=${year}_${month}\/\$file=${day}.csv
		wget --continue ${fname}
		echo ${fname}
		echo "${fname::-3}txt"
		csv_fname=da_loglist.cgi?dir=${year}_${month}%2F\$file=${day}.csv
		txt_fname=${year}${month}${day}.txt
		mv ${csv_fname} "$path$txt_fname"
	done
done


