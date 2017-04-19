# DSVR (Domain-Specific VPN Router)

## PURPOSE

If you're using a VPN service today, you may have found the following limitations:  

1) All or nothing. Either ALL traffic goes down the VPN or none - unable to be selective.  
2) Only one VPN at a time. Cannot selectively route certain sites down one VPN, and others down another VPN.  
3) Unless you've configured your VPN at the router level, it's likely that only a single device can use your VPN at one time.  

This project serves to address each of the above - see the FEATURES section.

Please review my blog post here http://darranboyd.wordpress.com/2013/07/05/selective-vpn-routing-solution-dsvr/  

## FEATURES

![SCREENSHOT](https://raw.github.com/dboyd13/DSVR/master/screenshots/dsvr-logical-v0.2.png)


1) Per-site VPN routing down specific VPN connections whilst all other traffic goes down the native internet connection, for example:  
```
    ussite1.com -> United States based VPN
    ussite2.com -> United States based VPN
    uksite1.com -> United Kingdom based VPN
    uksite2.com -> United Kingdom based VPN
    *.anaustraliansite.com -> Australian based VPN
    allothersites -> Native internet connection
```
2) Supports multiple "networks"
3) User specified DNS server for per-site DNS queries, for privacy from your ISP.  
4) Port Forwarding & uPnP on existing router/AP not affected (see TODO)  

## HOW IT WORKS

DSVR works by functioning as a nameserver on your network. Other machines on your network should use the DSVR machine as both their nameserver and default gateway. When a machine on your network wants to visit a site (Eg. ussite1.com) it will ask DSVR to resolve the address. To do this DSVR will check to see if it knows about ussite1.com. In our example above it sees that it needs to go via your United States based VPN as such it performs name resolution via your US based VPN's nameserver, adds a routing table entry on the DSVR machine for all the relevant ussite1.com IP addresses to go via the US based VPN's network device and forwards the resolution results back to the client machine. As the DSVR machine is configured as the default gateway when the client requests data from ussite1.com it'll be sent via the DSVR machine which will use the newly added routing tables to send the traffic over the appropraite VPN link.

If a machine on your network looks up asitenotinyourconfiguration.com DSVR will see that it has no record for this domain. As such it'll use your default nameserver to resolve the details of the domain and forward the results back to the requesting machine. It will not add an entry to your routing table. When the machine then tries to send traffic to asitenotinyourconfiguration.com the DSVR machine will receive the request and it will be handled via the default route on the DSVR machine (eg. Your standarad link to the internet).

The key parts here are that DSVR acts as a nameserver on your network and relies on other machines having the DSVR machine configured as both the nameserver and the default gateway.

## PRE-REQUISTES

1) A working Linux distribution
2) A working internet connection from the Linux machine
3) A working VPN connection from the Linux machine

## TESTED WITH

1) Raspbian on a Raspberry Pi

## INSTALLATION

Once you have your machine set up and runnig you'll want to install DSVR.
1) Install git; `sudo apt-get install git`
2) Grab DSVR from git; `git clone https://github.com/MrMDavidson/DSVR.git ~/dsvr/src`
3) Copy the sample config directory: `cp -R ~/dsvr/src/sample ~/dsvr/config`
4) (Optional) Install as a service
    1) Edit `~/dsvr/config/init-d-script` and modify the paths of `EXECUTABLEPATH` and `INIPATH` appropriately
    2) Copy the init-d-script to the appropriate location; `cp ~/dsvr/config/init-d-script /etc/init.d/dsvr`
    3) Install the service; `update-rc.d dsvr`

*Note:* Instead of running a service you can manually run dsvr with;

```shell
/path/to/dsvr.py --file /path/to/dsvr.ini
```

Additional arguments, and their help, can be found by running `/path/to/dsvr.py --help`

## CONFIGURATION

The majority of your configuration is done via editing your `dsvr.ini` file. This is broken into two sets of sections a "global" section and a series of network specific sections.

### SETTINGS OVERVIEW

| Setting          | Global | Applies to network | Meaning                                                                                                                                             |
|------------------|-------:|--------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| dns-server       | Yes    | Yes                | A nameserver to use for name resolution. If specified at a network level then requests for that network are resolved used that specific name server |
| ttl-override     | Yes    | Yes                | Overrides the DNS entry's time-to-live value when returned to clients                                                                               |
| dns-timeout      | Yes    | No                 | Number of seconds to wait before failing a name resolution from a server                                                                            |
| server-listen-ip | Yes    | No                 | Address to listen to DNS requests on. If absent will use 0.0.0.0 (ie. all interfaces)                                                               |
| device           | No     | Yes                | Device to route matching requests over                                                                                                              |
| whitelist        | No     | Yes                | Path to a file containing list of entries that should be routed via this network                                                                    |

### GLOBAL SETTINGS

Any of the entries listed above marked with "Global" can be specified at the "Global" level. If the setting (eg. "dns-server") can be applied at both a network and a global level then the global level operates as a default/fallback.

### NETWORK SETTINGS

Any of the entries listed above marked with "Applies to network" can be specified for each network. Each network section represents one link to the outside world. In the initial example your `dsvr.ini` file would have three network sections in addition to your global section eg.

```ini
[global]
...

[network-us-vpn]
device=tun0
...

[network-uk-vpn]
device=tun1
...

[network-au-vpn]
device=tun2

```

Whilst the network sections do not have to be a VPN link it is their intended purpose. As such you would want each network section to have its own `dns-server` entry which is your VPN provider's name server for that network. If you do not specify this then the DNS requests will be handled by the `dns-server` in the global section which may result in leaking of information.

#### WHITELIST FORMAT

The file referenced by the `whitelist` setting is a simple text file containing a list of domain names that are valid for that network section. Each domain name is specified on a newline. Comments may be specified by a `#` as the first character in the line.

If a domain name does not start with a `.` then it is considered an exact match (eg. `domain.com` would match `domain.com` but not `www.domain.com`). 

If the domain name starts with a `.` then it is a TLD match; any child domain of the record will be matched (eg. `.domain.com` would match `www.domain.com` and `domain.com`)

### ROUTE MANAGEMENT

In the `scripts` folder are two scripts;

#### `scripts/iprule-clear-table.sh`

Called on start up, once for each `[network-]` section with the name of the network as an argument (eg. `[network-test]` would be called with the argument `test`).

This script is responsible for clearing the state of the routing table for the given network.

#### `scripts/iprule-add-route.sh`

Everytime an DNS entry is resolved this script is called with the following arguments;

| Position | Name        | Purpose                                                                                                                                     |
|----------|-------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| $1       | IP Address  | The IP address of resolved DNS entry that a route is required for                                                                           |
| $2       | Device Name | The name of the device the route is required for (eg. `tun0`, from the `dsvr.ini` file for the network)                                     |
| $3       | Gateway     | If a default gateway exists for the device this route is for then this argument will be non-empty and be the address of the default gateway |


**CREDIT**

    Portions of code taken from the dnschef project (https://thesprawl.org/projects/dnschef/)
    
    Copyright (C) 2013 Peter Kacherginsky
    All rights Reserved
    
    Forked from https://github.com/dboyd13/DSVR

**LICENSE**

    DSVR (Domain Specific VPN Router)
    Copyright 2013 Darran Boyd
    
    dboyd13 [at @] gmail.com
    
    Licensed under the "Attribution-NonCommercial-ShareAlike" Vizsage
    Public License (the "License"). You may not use this file except
    in compliance with the License. Roughly speaking, non-commercial
    users may share and modify this code, but must give credit and 
    share improvements. However, for proper details please 
    read the full License, available at
        http://vizsage.com/license/Vizsage-License-BY-NC-SA.html 
    and the handy reference for understanding the full license at 
        http://vizsage.com/license/Vizsage-Deed-BY-NC-SA.html
    
    Unless required by applicable law or agreed to in writing, any
    software distributed under the License is distributed on an 
    "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, 
    either express or implied. See the License for the specific 
    language governing permissions and limitations under the License.

**LINKS**  

    - ASCII diagram (http://www.asciiflow.com/#Draw8450497916007412677/1697158644)
    - To properly calc memory usage due to disk caching - http://www.linuxatemyram.com/index.html
