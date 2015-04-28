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
import netifaces

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
            
            network = getRelevantNetwork(fallback, networks, str(d.q.qname))
            nameserver_tuple = random.choice(network.dnsservers).split('#')

            print "[ ] \"%s\" will route via %s. Looking up via %s" % (d.q.qname, network.devicename, nameserver_tuple[0] )
               
            response = self.proxyrequest(data, network.devicename, network.timeout, *nameserver_tuple)
            
            if network.isfallback == True:
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

                command = network.addroutecommand(str(item.rdata))
                print "[DB+] Adding %s via  \"%s\"" % (str(item.rdata), command)
                os.system(command)
                added_routes.append(str(item.rdata))

                if network.ttloverride != -1:
                    print "[ ] DNS response has a TTL of %r. Will override to %r" % (item.ttl , min(network.ttloverride, item.ttl) )
                    item.ttl = min(network.ttloverride, item.ttl)


            response = d.pack()
            
        return response         
        
    # Obtain a response from a real DNS server.
    def proxyrequest(self, request, device, timeout, host, port="53"):       
            reply = None
            try:
                    if self.server.ipv6:
                            sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                    else:
                            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                    #sock.setsockopt(socket.SOL_SOCKET, 25, device)

                    if timeout != None and timeout > 0:
                        sock.settimeout(timeout)

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
    def __init__(self, server_address, RequestHandlerClass, nametodns, fallback, networks, ipv6):
        self.nametodns  = nametodns
        self.fallback = fallback
        self.networks = networks
        self.ipv6        = ipv6
        self.address_family = socket.AF_INET6 if self.ipv6 else socket.AF_INET

        SocketServer.UDPServer.__init__(self,server_address,RequestHandlerClass)

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    
    # Override default value
    allow_reuse_address = True

    # Override SocketServer.TCPServer to add extra parameters
    def __init__(self, server_address, RequestHandlerClass, nametodns, fallback, networks, ipv6):
        self.nametodns  = nametodns
        self.nameservers = nameservers
        self.ttloverride = ttloverride
        self.ipv6        = ipv6
        self.address_family = socket.AF_INET6 if self.ipv6 else socket.AF_INET

        SocketServer.TCPServer.__init__(self,server_address,RequestHandlerClass) 

    @property
    def ttloverride(self):
        return self.ttloverride

def getRelevantNetwork(fallback, networks, domain):
    extracted = tldextract.extract(str(domain))
    tld = extracted.domain + "." + extracted.suffix
    if len(extracted.subdomain) > 0:
        full = extracted.subdomain + "." + tld
    else:
        full = tld

    for network in networks:
        for regular in network.domains:
            if len(regular) == 0: continue
            
            if regular[0] == ".":
                regular = regular[1:]
                # Use TLD to match
                if regular == tld:
                    print "[ ] TLD style match for \"%s\" against \"%s\". Will route via %s" % (full, regular, network.devicename)
                    return network
            else:
                # Use exact match
                if regular == full:
                        print "[ ] Exact  match for \"%s\" against \"%s\". Will route via %s" % (full, regular, network.devicename)
                        return network
        
    return fallback
        
# Initialize and start dsvr        
def start_cooking(interface, nametodns, fallback, networks, tcp=False, ipv6=False, port="53"):
    try:
        if tcp:
            print "[*] dsvr is running in TCP mode"
            server = ThreadedTCPServer((interface, int(port)), TCPHandler, nametodns, fallback, networks, ipv6)
        else:
            server = ThreadedUDPServer((interface, int(port)), UDPHandler, nametodns, fallback, networks, ipv6)

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

class NetworkInfo:
    def __init__(self, dnsservers, domainlistfile, devicename, ttloverride, timeout, devicegateway = '', isfallback = False):
        self._dnsservers = dnsservers
        self._devicename = devicename
        self._ttloverride = ttloverride
        self._isfallback = isfallback
        self._timeout = timeout
        self._devicegateway = devicegateway

        if domainlistfile != None:
            file = open(domainlistfile, 'r')
            self._domains = []
            for line in file:
                line = line.rstrip()
                if len(line) == 0: continue
                if line[0] == '#': continue
                print "[ ] Have rule for \"%s\"" % line

                self._domains.append(line)

            file.close()

    @property
    def dnsservers(self):
        return self._dnsservers

    @property
    def domains(self):
        return self._domains

    @property
    def devicename(self):
        return self._devicename

    @property
    def ttloverride(self):
        return self._ttloverride

    @property
    def isfallback(self):
        return self._isfallback

    @property
    def timeout(self):
        return self._timeout

    @property
    def devicegateway(self):
        return self._devicegateway

    def addroutecommand(self, address):
        return "sudo " + os.path.abspath(os.path.dirname(sys.argv[0])) + "/scripts/addregularroute.sh " + address + " " + self.devicename + " " + self.devicegateway
    
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
    rungroup.add_option("-i","--interface", metavar="0.0.0.0 or ::1", action="store", help='Define an interface to use for the DNS listener. By default, the tool uses 0.0.0.0 for IPv4 mode and ::1 for IPv6 mode.')
    rungroup.add_option("-t","--tcp", action="store_true", default=False, help="Use TCP DNS proxy instead of the default UDP.")
    rungroup.add_option("-6","--ipv6", action="store_true", default=False, help="Run in IPv6 mode.")
    rungroup.add_option("-p","--port", action="store", metavar="53", default="53", help='Port number to listen for DNS requests.')
    rungroup.add_option("-q", "--quiet", action="store_false", dest="verbose", default=True, help="Don't show headers.")
    parser.add_option_group(rungroup)

    (options,args) = parser.parse_args()
 
    # Print program header
    if options.verbose:
        print header

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
        print "[*] Using external econfig file: %s" % options.file

        fallbackdnsservers = []
        fallbackdnsservers.append(config.get('Global', 'dns-server'))
        if config.has_option("Global", "ttl-override") == False:
            fallbackttloverride = -1
        else:
            fallbackttloverride = config.getint('Global', 'ttl-override')
        if config.has_option("Global", "dns-timeout") == False:
            fallbackdnstimeout = -1
        else:
            fallbackdnstimeout = config.getint("Global", "dns-timeout")

        if config.has_option("Global", "server-listen-ip") == True:
            if options.interface:
                print "[ ] Interface was specified in INI file as %s but overriden on the command line to %s" % (config.get("Global", "server-listen-ip"), options.interface)
            else:
                print "[ ] Interface was specified in INI file as %s" % config.get("Global", "server-listen-ip")
                options.interface = config.get("Global", "server-listen-ip")
                

        fallback = NetworkInfo(fallbackdnsservers, None, 'Global', fallbackttloverride, fallbackdnstimeout, None, True)

        networks = []
        inetgateways = netifaces.gateways()[netifaces.AF_INET]

        for section in config.sections():
            if section.startswith("network-") == False:
                continue
            networkname = section.replace("network-", "")
            print "File has section \"%s\" => %s" % ( section, networkname)

            device = config.get(section, "device")
            
            for gateway in inetgateways:
                if gateway[1] == device:
                    devicegateway = gateway[0]

            if devicegateway == None:
                print "[WARN] Routes added for %s will not have a gateway set. This may cause issues" % device
            else:
                print "[ ] Routes added for %s will travel via %s" % (device, devicegateway)
            
            if config.has_option(section, "dns-server") == False:
                print "[WARN] DNS Server for %s is not set. Will use default of %s. This may allow your DNS requests to leak" % (networkname, ", ".join(fallbackdnsservers))
                dnsservers = fallbackdnsservers
            else:
                dnsservers = []
                dnsservers.append(config.get(section, "dns-server"))
                print "[ ] %s will look up via %s" % (networkname, ", ".join(dnsservers))

            if config.has_option(section, "ttl-override") == False:
                print "[INFO] TTL override for %s is not set. Will use default of %i" % (section, fallbackttloverride)
                ttloverride = fallbackttloverride
            else:
                ttloverride = config.getint(section, "ttl-override")
                
            if config.has_option(section, "dns-timeout") == False:
                print "[INFO] DNS timeout for %s is not set. Will use default of %i" % (section, fallbackdnstimeout)
                dnstimeout = fallbackdnstimeout
            else:
                dnstimeout = config.getint(section, "dns-timeout")
                            
            whitelistpath = config.get(section, "whitelist")

            current = NetworkInfo(dnsservers, whitelistpath, device, ttloverride, dnstimeout, devicegateway)
            networks.append(current)
                                
    print "[*] Clearing existing IP Rules"
    command = os.path.abspath(os.path.dirname(sys.argv[0])) + "/scripts/iprule-clear-table.sh "
    os.system(command)
    
    # Add selected DNS servers to route via the VPN
    for network in networks:
        for server in network.dnsservers:
            print "[*] Adding route for %s via %s" % (server, network.devicename)

            command = network.addroutecommand(server)
            print "[ ] Calling %s" % ( command )
            os.system(command)
   
    # Launch dsvr
    start_cooking(interface=options.interface, nametodns=nametodns, fallback=fallback, networks=networks, tcp=options.tcp, ipv6=options.ipv6, port=options.port)


