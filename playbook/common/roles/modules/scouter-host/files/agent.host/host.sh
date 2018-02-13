#!/bin/bash
# Source function library
 
source /etc/rc.d/init.d/functions
 
export PATH=$PATH:$JAVA_HOME/bin
export SCOUTER_HOME=$SCOUTER_HOME
export JAVA_OPTS="-Dscouter.config=${SCOUTER_HOME}/conf/scouter.conf"
 
nohup java ${JAVA_OPTS} -classpath ${SCOUTER_HOME}/scouter.host.jar scouter.boot.Boot ${SCOUTER_HOME}/lib > nohup.out &
 
sleep 1
tail -100 nohup.out