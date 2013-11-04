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

# Only required for more convenient local development.

import sys, os
sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/lib')

from cloudagents import CloudAgent
from time import sleep

ca = CloudAgent()

ca.required_config = {
	"name": "Count Up",
	"version": "0.1.0",
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This script counts up from 0 by the count number given, storing the end number in a datastore.  If the datastore contains a number, it starts there instead of 0.""",
	"config":
		[{
			"name": "count",
			"regexp": "^\d+$",
			"title": "Count",
			"description": "Number to count up.",
			"type": "string",
			"required": True
		}
		]
	}

def agent():

	count = int(ca.conf['count'])
	if ca.datastore:
		start = int(ca.datastore)
	else:
		start = 0

	for i, num in enumerate(range(start+1,start+count+1,1)):
		sleep(1)
		percent = int((float(i+1)/float(count))*100.0)
		ca.log(str(num),"Counted up to "+str(num)+".",percent)
	
	ca.store(str(num))


ca.run(agent)
