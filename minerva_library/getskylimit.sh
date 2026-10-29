#!/bin/sh
ssh -o ConnectTimeout=3 observer@flwo48.sao.arizona.edu grep me_sky_limit /home/petr/rts2-sys/run/me_autosave
