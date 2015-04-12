#!/bin/sh

route add -host $1 gw 10.1.101.1 dev eth0
