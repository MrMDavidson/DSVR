#!/bin/sh

IPADDR=$1
DEVNAME=$2
GATEWAY=$3

if [ -z "$GATEWAY" ]; then
    route add -host $IPADDR dev $DEVNAME
    #ip route add $IPADDR dev $DEVNAME table $DEVNAME
else
    #ip route add $IPADDR via $GATEWAY dev $DEVNAME table $DEVNAME
    route add -host $IPADDR gw $GATEWAY dev $DEVNAME
fi
