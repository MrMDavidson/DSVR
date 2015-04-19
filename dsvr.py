#!/usr/bin/env python
#
# DSVR (Domain Specific VPN Router)
# Copyright 2013 Darran Boyd
#
# dboyd13 [at @] gmail.com
#
# Licensed under the "Attribution-NonCommercial-ShareAlike" Vizsage
# Public License (the "License"). You may not use this file except
# in compliance with the License. Roughly speaking, non-commercial
# users may share and modify this code, but must give credit and 
# share improvements. However, for proper details please 
# read the full License, available at
#     http://vizsage.com/license/Vizsage-License-BY-NC-SA.html 
# and the handy reference for understanding the full license at 
#     http://vizsage.com/license/Vizsage-Deed-BY-NC-SA.html
#
# Unless required by applicable law or agreed to in writing, any
# software distributed under the License is distributed on an 
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, 
# either express or implied. See the License for the specific 
# language governing permissions and limitations under the License.
#
# Portions of code from the work of Peter Kacherginsky's dnschef - http://thesprawl.org/projects/dnschef/:
# iphelix [at] thesprawl.org.
#
# Copyright (C) 2013 Peter Kacherginsky
# All rights reserved.
#

from optparse import OptionParser,OptionGroup
from ConfigParser import ConfigParser
from lib.dnslib import *
from lib.IPy import IP

import threading, random, operator, time
import SocketServer, socket, sys, os, re
import tldextract,commands
import binascii

class DNSHandler():
           
    def parse(self,data):
        response = ""
    
        try:
            # Parse data as DNS        
            d = DNSRecord.parse(data)

        except Exception, e:
            print "[%s] %s: ERROR: %s" % (time.strftime("%H:%M:%S"), self.client_address[0], "invalid DNS request")

        # Proxy the request
        else:
            print "[ ] %s wants to look up %s" % (self.client_address[0], str(d.q.qname))
            
            isRegular = False
                    
            if isRegularDomain(regulardomains, str(d.q.qname)) == True:
                nameserver_tuple = random.choice(self.server.nameservers).split('#')
                isRegular = True
            else:
                nameserver_tuple = random.choice(db_dns_vpn_server).split('#') 

            print "[ ] \"%s\" is considered a %s domain. Looking up via %s" % (d.q.qname, "regular" if isRegular == True else "VPN", nameserver_tuple[0] )
               
            response = self.proxyrequest(data,*nameserver_tuple)

            if isRegular == False:
                return response

            d = DNSRecord.parse(response)
           
            for item in d.rr:               
                try:
                    socket.inet_aton(str(item.rdata))
                except:
                    print "[DB] Unable to inet_aton %s" % str(item.rdata)
                    continue
                if str(item.rdata) in added_routes:
                    print "[DB] Have previously added %s. Skipping" % str(item.rdata)
                    continue

                command = "sudo " + os.path.abspath(os.path.dirname(sys.argv[0])) + "/scripts/addregularroute.sh " + str(item.rdata)
                print "[DB+] Adding %s via  \"%s\"" % (str(item.rdata), command)
                os.system(command)
                added_routes.append(str(item.rdata))

                if self.server.ttloverride != -1:
                    print "[ ] DNS response has a TTL of %r. Will override to %r" % (item.ttl , min(self.server.ttloverride, item.ttl) )
                    item.ttl = min(self.server.ttloverride, item.ttl)


            response = d.pack()
            
        return response         
        
    # Obtain a response from a real DNS server.
    def proxyrequest(self, request, host, port="53"):       
            reply = None
            try:
                    if self.server.ipv6:
                            sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                    else:
                            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                    sock.settimeout(3.0)

                    # Send the proxy request to a randomly chosen DNS server
                    sock.sendto(request, (host, int(port)))
                    reply = sock.recv(1024)
                    sock.close()

            except Exception, e:
                    print "[!] Could not proxy request: %s" % e
            else:
                    return reply 

# UDP DNS Handler for incoming requests
class UDPHandler(DNSHandler, SocketServer.BaseRequestHandler):

    def handle(self):
        (data,socket) = self.request
        response = self.parse(data)
        
        if response:
            socket.sendto(response, self.client_address)

# TCP DNS Handler for incoming requests            
class TCPHandler(DNSHandler, SocketServer.BaseRequestHandler):

    def handle(self):
        data = self.request.recv(1024)
        
        # Remove the addition "length" parameter used in
        # TCP DNS protocol
        data = data[2:] 
        response = self.parse(data)
        
        if response:
            # Calculate and add the additional "length" parameter
            # used in TCP DNS protocol 
            length = binascii.unhexlify("%04x" % len(response))            
            self.request.sendall(length+response)            

class ThreadedUDPServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):

    # Override SocketServer.UDPServer to add extra parameters
    def __init__(self, server_address, RequestHandlerClass, nametodns, nameservers, ipv6, ttloverride):
        self.nametodns  = nametodns
        self.nameservers = nameservers
        self.ttloverride = ttloverride
        self.ipv6        = ipv6
        self.address_family = socket.AF_INET6 if self.ipv6 else socket.AF_INET

        SocketServer.UDPServer.__init__(self,server_address,RequestHandlerClass)

    @property
    def ttloverride(self):
        return self.ttloverride

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    
    # Override default value
    allow_reuse_address = True

    # Override SocketServer.TCPServer to add extra parameters
    def __init__(self, server_address, RequestHandlerClass, nametodns, nameservers, ipv6, ttloverride):
        self.nametodns  = nametodns
        self.nameservers = nameservers
        self.ttloverride = ttloverride
        self.ipv6        = ipv6
        self.address_family = socket.AF_INET6 if self.ipv6 else socket.AF_INET

        SocketServer.TCPServer.__init__(self,server_address,RequestHandlerClass) 

    @property
    def ttloverride(self):
        return self.ttloverride

def isInterestingDomain(input_dict, searchstr):
    for index in input_dict:
        for item in input_dict[index]:
            if item in searchstr:
                list = [1,index]
                return list
    list = [0]
    return list

def isRegularDomain(regularDomains, domain):
    extracted = tldextract.extract(str(domain))
    tld = extracted.domain + "." + extracted.suffix
    if len(extracted.subdomain) > 0:
        full = extracted.subdomain + "." + tld
    else:
        full = tld

    for regular in regularDomains:
        if len(regular) == 0: continue
        
        if regular[0] == ".":
            regular = regular[1:]
            # Use TLD to match
            if regular == tld:
                print "[ ] TLD style match for \"%s\" against \"%s\". Will route normally" % (full, regular)
                return True
        else:
            # Use exact match
            if regular == full:
                    print "[ ] Exact  match for \"%s\" against \"%s\". Will route normally" % (full, regular)
                    return True
        
    return False

def getRegularTrafficDomains(trafficFilePath):
    file = open(trafficFilePath, 'r')
    domains = []
    for line in file:
        line = line.rstrip()
        if len(line) == 0: continue
        print "[ ] Have rule for \"%s\"" % line

        domains.append(line)

    file.close()

    return domains 
        
# Initialize and start dsvr        
def start_cooking(interface, nametodns, nameservers, tcp=False, ipv6=False, port="53", ttloverride=-1):
    try:
        if tcp:
            print "[*] dsvr is running in TCP mode"
            server = ThreadedTCPServer((interface, int(port)), TCPHandler, nametodns, nameservers, ipv6, ttloverride)
        else:
            server = ThreadedUDPServer((interface, int(port)), UDPHandler, nametodns, nameservers, ipv6, ttloverride)

        # Start a thread with the server -- that thread will then start one
        # more threads for each request
        server_thread = threading.Thread(target=server.serve_forever)
        # Exit the server thread when the main thread terminates
        server_thread.daemon = True
        server_thread.start()
        
        # Loop in the main thread
        while True: time.sleep(100)

    except (KeyboardInterrupt, SystemExit):
        server.shutdown()
        print "[*] dsvr is shutting down."
        sys.exit()
    
if __name__ == "__main__":

    header  = "##########################################\n"
    header += "#              dsvr v0.1                 #\n"
    header += "#                  darranboyd.com        #\n"
    header += "##########################################\n"
    

    # Parse command line arguments
    parser = OptionParser(usage = "dsvr.py [options]:\n" + header, description="" )
    
    fakegroup = OptionGroup(parser, "Fake DNS records:")

    fakegroup.add_option('--file', action="store", help="Specify a file containing a list of DOMAIN=IP pairs (one pair per line) used for DNS responses. For example: google.com=1.1.1.1 will force all queries to 'google.com' to be resolved to '1.1.1.1'. IPv6 addresses will be automatically detected. You can be even more specific by combining --file with other arguments. However, data obtained from the file will take precedence over others.")
   
    rungroup = OptionGroup(parser,"Optional runtime parameters.")
    rungroup.add_option("--nameservers", metavar="8.8.8.8#53 or 2001:4860:4860::8888", default='8.8.8.8', action="store", help='A comma separated list of alternative DNS servers to use with proxied requests. Nameservers can have either IP or IP#PORT format. A randomly selected server from the list will be used for proxy requests when provided with multiple servers. By default, the tool uses Google\'s public DNS server 8.8.8.8 when running in IPv4 mode and 2001:4860:4860::8888 when running in IPv6 mode.')
    rungroup.add_option("-i","--interface", metavar="127.0.0.1 or ::1", default="127.0.0.1", action="store", help='Define an interface to use for the DNS listener. By default, the tool uses 127.0.0.1 for IPv4 mode and ::1 for IPv6 mode.')
    rungroup.add_option("-t","--tcp", action="store_true", default=False, help="Use TCP DNS proxy instead of the default UDP.")
    rungroup.add_option("-6","--ipv6", action="store_true", default=False, help="Run in IPv6 mode.")
    rungroup.add_option("-p","--port", action="store", metavar="53", default="53", help='Port number to listen for DNS requests.')
    rungroup.add_option("-q", "--quiet", action="store_false", dest="verbose", default=True, help="Don't show headers.")
    rungroup.add_option("-r", "--regulardomains", action="store", help="Path to a new line separated list of domains to skip the VPN")
    parser.add_option_group(rungroup)

    (options,args) = parser.parse_args()
 
    # Print program header
    if options.verbose:
        print header

    if options.regulardomains is None:
        print "Must specify a file containing a list of regular domains to route via the unenecrypted link"
        sys.exit()

    regulardomains = getRegularTrafficDomains(options.regulardomains) 
    db_dns_vpn_server = []
    db_dns_upstream_server = []
    added_routes = []
    
    # Main storage of domain filters
    # NOTE: RDMAP is a dictionary map of qtype strings to handling classses
    nametodns = dict()
    for qtype in RDMAP.keys():
        nametodns[qtype] = dict()
    
    # Notify user about alternative listening port
    if options.port != "53":
        print "[*] Listening on an alternative port %s" % options.port

    print "[*] dsvr started on interface: %r " % options.interface

    # External file definitions
    if options.file:
        config = ConfigParser()
        if "/" not in options.file:
            options.file = os.path.abspath(os.path.dirname(sys.argv[0])) + "/" + options.file
        config.read(options.file)
        print "[*] Using external config file: %s" % options.file
            
        db_dns_upstream_server.append(config.get('Global','dns-upstream-server'))
        print "[*] Using the following nameservers for un-interesting domains: %s" % ", ".join(db_dns_upstream_server)
        nameservers = db_dns_upstream_server
        db_dns_vpn_server.append(config.get('Global','dns-vpn-server'))
        print "[*] Using the following nameservers for interesting domains: %s" % ", ".join(db_dns_vpn_server)
        db_ttl_override_value = config.get('Global','ttl-override-value')
        if db_ttl_override_value != None:
            db_ttl_override_value = int(db_ttl_override_value)
            print "[*] TTL overide value for interesting domains: %i" % db_ttl_override_value
        else:
            db_ttl_override_value = -1
                                
    print "[*] Clearing existing IP Rules"
    command = os.path.abspath(os.path.dirname(sys.argv[0])) + "/scripts/iprule-clear-table.sh "
    os.system(command)
    
    # Add selected DNS servers to route via the VPN
##    if interestingdomainsng:
##        for interfacename in interestingdomainsng:
##            intname = interfacename
##            break 
## 
##        for item in db_dns_vpn_server:
##            print "[*] Routing DNS server (%s) via first specificed int (%s)" % (item, intname)
##            command = "sudo " + os.path.abspath(os.path.dirname(sys.argv[0])) + "/scripts/addroutetorule.sh " + item + " " + intname #DB
##            os.system(command)
   
    # Launch dsvr
    start_cooking(interface=options.interface, nametodns=nametodns, nameservers=nameservers, tcp=options.tcp, ipv6=options.ipv6, port=options.port, ttloverride=db_ttl_override_value)


