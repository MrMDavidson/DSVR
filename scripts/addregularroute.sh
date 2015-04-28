#!/bin/sh

IPADDR=$1
DEVNAME=$2
GATEWAY=$3

if [ -z "$GATEWAY" ]; then
    route add -host $IPADDR dev $DEVNAME
else
    route add -host $IPADDR gw $GATEWAY dev $DEVNAME 
fi

#ip route add $1 via 10.1.101.1 dev eth0 table eth0
#route add -host $IPADDR gw 10.1.101.1 dev $DEVNAME
#ip route add $IPADDR dev $DEVNAME table $DEVNAME
#route add -host $IPADDR dev $DEVNAME
