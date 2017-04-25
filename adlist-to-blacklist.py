#!/usr/bin/env python

import urllib2
import urlparse
import os
from optparse import OptionParser

def readFromFileOrUrl(path):
    content = []
    if os.path.isfile(path) == True:
        with open(path, 'r') as file:
            content = file.readlines()
    else:
        response = urllib2.urlopen(path)
        content = response.read().splitlines()

    return content

def getEntriesFromUrl(sourceUrl):
    entry = []
    content = readFromFileOrUrl(sourceUrl)

    for line in content:
        line = line.strip()
        if len(line) == 0: continue
        if line[0] == '#': continue

        components = line.split()
        host = ""
        if len(components) == 1:
            # No spaces? Probably a straight domain name to block
            host = line
        else:
            # Spaces? Presume it's a host entry - take the hostname (second entry)
            host = components[1]

        entry.append(host)

    return entry

def beginContainerDownload(sourceUrl, outputFile):
    content = readFromFileOrUrl(sourceUrl)
    blocklist = set()

    for line in content:
        line = line.strip()
        if len(line) == 0: continue
        if line[0] == '#': continue

        print 'Fetching from child url: %s' % line
        childEntry = getEntriesFromUrl(line)
        print '\tHas %i block entries' % len(childEntry)

        for entry in childEntry:
            blocklist.add(entry)

    print "Have %s block items in total!" % len(blocklist)

    with open(outputFile, 'w') as output:
        for entry in blocklist:
            output.write(entry)
            output.write("\n")

    return

if __name__ == "__main__":
    parser = OptionParser("adlist-to-blacklist [options]:\n")
    parser.add_option("-i", "--input", action="store", help="Path a file (can be a URL) containing a list of URLs containing ad block lists")
    parser.add_option("-o", "--output", action="store", default="blocklist.txt", help="Path to write the result of the ad block lists to")

    (options, args) = parser.parse_args()
    
    if options.input == None:
        print 'No input argument defined. Run with --help to see options'
    else:
        print 'Reading from %s and writing to %s' % (options.input, options.output)
        beginContainerDownload(options.input, options.output)