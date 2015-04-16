#!/bin/sh

#ip route add $1 via 10.1.101.1 dev eth0 table eth0
route add -host $1 gw 10.1.101.1 dev eth0
