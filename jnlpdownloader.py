#!/usr/bin/env python3

# Josh Berry
# CodeWatch
# August 2014

import argparse
import importlib
import re
import requests
import string
import sys
import random
import os
from requests.auth import HTTPBasicAuth
from requests.auth import HTTPDigestAuth

# use lxml if available (for error recovery) but fallback to stdlib
try:
    ET = importlib.import_module("lxml.etree")
    xml_parser = ET.XMLParser(recover=True)
except ModuleNotFoundError:
    from xml.etree import ElementTree as ET

    xml_parser = ET.XMLParser()

# Get all the arguments for the tool
parser = argparse.ArgumentParser(
    description="Download JAR files associated with a JNLP file.",
    epilog="Example: jnlpdownloader.py https://www.example.com/java/jnlp/sample.jnlp",
)
link_group = parser.add_mutually_exclusive_group(required=True)
link_group.add_argument(
    "url", nargs="?", help="the full URL to the JNLP file (must include http(s)://)"
)
link_group.add_argument("--link", help="same as <url> (for backwards compatibility)")
parser.add_argument(
    "-k",
    "--insecure",
    action="store_true",
    help="disable server TLS certificate validation for downloads",
)
parser.add_argument(
    "--ntlmuser",
    help="use NTLM authentication with this username (format of domain \\ username)",
)
parser.add_argument("--ntlmpass", help="use NTLM authentication with this password")
parser.add_argument("--basicuser", help="use BASIC authentication with this username")
parser.add_argument("--basicpass", help="use BASIC authentication with this password")
parser.add_argument("--digestuser", help="use DIGEST authentication with this username")
parser.add_argument("--digestpass", help="use DIGEST authentication with this password")
parser.add_argument("--cookie", help="use a previously established sessions cookie")

# Stick arguments in a variable and then create a session
args = vars(parser.parse_args())
start_url = args["url"] or args["link"]
r = ""
session = requests.Session()

# Disable the warnings that appear on every request when certificate validation is disabled
if args["insecure"]:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Random value for directory creation
randDir = "".join(
    random.SystemRandom().choice(string.ascii_lowercase + string.digits)
    for _ in range(10)
)

# Check to see if BASIC/DIGEST/NTLM/Cookie authentication is being performed
# If so, pass credentials to session, if not, just connect to JNLP URL
cookies = {}
if args["ntlmuser"] != None and args["ntlmpass"] != None:
    from requests_ntlm import HttpNtlmAuth

    session.auth = HttpNtlmAuth(args["ntlmuser"], args["ntlmpass"], session)
elif args["basicuser"] != None and args["basicpass"] != None:
    session.auth = HTTPBasicAuth(args["basicuser"], args["basicpass"])
elif args["digestuser"] != None and args["digestpass"] != None:
    session.auth = HTTPDigestAuth(args["digestuser"], args["digestpass"])
elif args["cookie"] != None:
    # Check to see if the cookie has a semicolon, if so there might be multiple cookies
    if ";" in args["cookie"]:
        cookielist = args["cookie"].split(";")

        # Loop through list of cookies
        for jnlpcookies in cookielist:
            # If there isn't an equal and some sort of content then it isn't a valid cookie, otherwise add to list of cookies
            if re.search("[a-zA-Z0-9]", jnlpcookies) and "=" in jnlpcookies:
                cookieparts = jnlpcookies.split("=")
                cookies[cookieparts[0]] = cookieparts[1]

    else:
        # Split cookie at = into name/value pair, otherwise ignore the malformed cookie
        if "=" in args["cookie"]:
            cookielist = args["cookie"].split("=")
            cookies[cookielist[0]] = cookielist[1]

r = session.get(start_url, cookies=cookies, verify=not args["insecure"])

# If the status code is not 200, the file was likely inaccessible so we exit
if r.status_code != 200:
    print("[*]", r.status_code, r.reason)
    print("[*] Link was inaccessible, exiting.")
    exit(0)

try:
    # Attempt to read the JNLP XML
    xmltree = ET.ElementTree(ET.XML(r.content, xml_parser))

    # Get the XML document structure and pull out the main link
    xmlroot = xmltree.getroot()
    jnlpurl = xmlroot.attrib["codebase"] + "/"
except Exception as exception:
    print("[*]", exception)
    print("[*] JNLP file was misformed, exiting.")
    if "lxml" not in sys.modules:
        print(
            "[*] To enable automatic recovery from some XML errors, install the 'lxml' package with 'pip install lxml'"
        )
    exit(0)

# If the JNLP file was good, create directory to store JARs or default to current
path = os.path.join(os.getcwd(), randDir)
try:
    if not os.path.exists(path):
        os.mkdir(path)
    else:
        print("[*] Random directory already exists, defaulting to current.")
        randDir = "."
except:
    print("[*] Failed to create random directory, defaulting to current.")
    randDir = "."

jnlplinks = []

# Loop through each JAR listed in the JNLP file
for jars in xmlroot.iter("jar"):
    # Get the file, path, and URI
    jnlpfile = jars.get("href").rsplit("/")[1]
    jnlppath = jars.get("href").rsplit("/")[0] + "/"
    jnlpuri = jars.get("href")

    # If the JAR has version info, then store it as we might need to use it
    if jars.get("version") is None:
        jnlpalt = None
        jnlpver = None
        altfile = None
    else:
        jnlpalt = (
            jnlppath + jnlpfile.rsplit(".jar")[0] + "__V" + jars.get("version") + ".jar"
        )
        altfile = jnlpfile.rsplit(".jar")[0] + "__V" + jars.get("version") + ".jar"
        jnlpver = jnlpuri + "?version-id=" + jars.get("version")

    # Add each JAR URI, Version, Filename, Alternate URI, and alternate filename to a list
    # These alternates are based on behavior I have seen where Java uses the version
    # information in the file name
    jnlplinks.append([jnlpuri, jnlpver, jnlpfile, jnlpalt, altfile])

# Loop through each Native Library listed in the JNLP file
for nativelibs in xmlroot.iter("nativelib"):
    # Get the file, path, and URI
    jnlpfile = nativelibs.get("href").rsplit("/")[1]
    jnlppath = nativelibs.get("href").rsplit("/")[0] + "/"
    jnlpuri = nativelibs.get("href")

    # If the Native Library has version info, then store it as we might need to use it
    if nativelibs.get("version") is None:
        jnlpalt = None
        jnlpver = None
        altfile = None
    else:
        jnlpalt = (
            jnlppath
            + jnlpfile.rsplit(".jar")[0]
            + "__V"
            + nativelibs.get("version")
            + ".jar"
        )
        altfile = (
            jnlpfile.rsplit(".jar")[0] + "__V" + nativelibs.get("version") + ".jar"
        )
        jnlpver = jnlpuri + "?version-id=" + nativelibs.get("version")

    # Add each JAR URI, Version, Filename, Alternate URI, and alternate filename to a list
    # These alternates are based on behavior I have seen where Java uses the version
    # information in the file name
    jnlplinks.append([jnlpuri, jnlpver, jnlpfile, jnlpalt, altfile])

# Loop through the list of lists with all the URI, version, etc info
for link in jnlplinks:
    # Make a request for the file
    print("[+] Attempting to download: " + jnlpurl + link[0])
    jnlpresp = session.get(jnlpurl + link[0])

    # If the request succeeded, then write the JAR to disk
    if jnlpresp.status_code == 200:
        print("[-] Saving file: " + link[2] + " to " + randDir)
        output = open(randDir + "/" + link[2], "wb")
        output.write(jnlpresp.content)
        output.close()
    else:
        # If the straight request didn't succeed, try to download with version info
        if link[1] != None:
            # Make a request for the file
            print("[+] Attempting to download: " + jnlpurl + link[1])
            jnlpresp = session.get(jnlpurl + link[1])

            # If the request succeeded, then write the JAR to disk
            if jnlpresp.status_code == 200:
                print("[-] Saving file: " + link[2] + " to " + randDir)
                output = open(randDir + "/" + link[2], "wb")
                output.write(jnlpresp.content)
                output.close()

        # If the straight request didn't succeed, try to download with alternate name
        if link[3] != None and link[4] != None:
            # Make a request for the file
            print("[+] Attempting to download: " + jnlpurl + link[3])
            jnlpresp = session.get(jnlpurl + link[3])

            # If the request succeeded, then write the JAR to disk
            if jnlpresp.status_code == 200:
                print("[-] Saving file: " + link[4] + " to " + randDir)
                output = open(randDir + "/" + link[4], "wb")
                output.write(jnlpresp.content)
                output.close()
