#!/bin/sh

IPADDR=$1
DEVNAME=$2
GATEWAY=$3

if [ -z "$GATEWAY" ]; then
    ip route add $IPADDR dev $DEVNAME table $DEVNAME
else
    ip route add $IPADDR via $GATEWAY dev $DEVNAME table $DEVNAME
fi
