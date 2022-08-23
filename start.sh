#!/bin/bash
sleep 10

cd /usr/local/src

python3 bot.py &
  
python3 events.py &

crond -l 0 -f
