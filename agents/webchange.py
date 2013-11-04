#!/usr/bin/env python

# Copyright 2013 Hewlett-Packard Development Company, L.P.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import sys, os
sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/lib')

from cloudagents import CloudAgent

ca = CloudAgent()

ca.required_config = {
	"name": "Web Page Change Check",
	"version": "0.1.0",
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This script notifies a user if a web page content changes.""",
	"config":
		[{
			"name": "url",
			"regexp": "^.+$",
			"title": "URL",
			"description": "HTTP or HTTPS URL to check.",
			"type": "string",
			"required": True
		},{
			"name": "element",
			"regexp": "^.+$",
			"title": "Element",
			"description": "HTML Element to check for changes.",
			"type": "string",
			"required": False
		},{
			"name": "class",
			"regexp": "^.+$",
			"title": "Class",
			"description": "HTML Element Class to check for changes.",
			"type": "string",
			"required": False
		},{
			"name": "id",
			"regexp": "^.+$",
			"title": "ID",
			"description": "HTML Element ID to check for changes.",
			"type": "string",
			"required": False
		}
		]
	}

def agent():

	from bs4 import BeautifulSoup
	import urllib2

	url = ca.conf.get('url')
	ca.log("Grabbing "+url)
	webpage = urllib2.urlopen(url)
	rawcontent = webpage.read()
	soup = BeautifulSoup(rawcontent)
	content = ''
	oldcontent = ca.datastore

	if (ca.conf.get('element') and ca.conf.get('class') and ca.conf.get('id')):
		for tag in soup.find_all(ca.conf.get('element'), class_=ca.conf.get('class'), id=ca.conf.get('id')):
			content += str(tag)
	elif (ca.conf.get('element') and ca.conf.get('class')):
		for tag in soup.find_all(ca.conf.get('element'), class_=ca.conf.get('class')):
			content += str(tag)
	elif (ca.conf.get('element') and ca.conf.get('id')):
		for tag in soup.find_all(ca.conf.get('element'), id=ca.conf.get('id')):
			content += str(tag)
	else:
		content = rawcontent

	if (content != oldcontent):
		ca.log("Content didn't match!")
		ca.email("Web Page Changed: "+ca.conf['url'],'''
	The web page '%s' changed!  New Content:

	%s
	''' % (ca.conf['url'], content))
	ca.store(content)

ca.run(agent)
