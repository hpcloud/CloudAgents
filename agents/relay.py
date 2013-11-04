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
import urllib2
import json

ca = CloudAgent()

ca.required_config = {
	"name": "Relay",
	"version": "0.1.0",
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This agent schedules another single run task some time in the future with the same name, interval, etc.  It's a demo for agents interacting directly with the agents service.""",
	"config":
		[{
			"name": "interval",
			"regexp": "^\d+$",
			"title": "Interval",
			"description": "Time between agent executions.",
			"type": "string",
			"required": True
		}
		]
	}

def agent():

	# Log my config.
	response = agent_query(url=ca.service['api_url'],
				path="/tasks/"+str(ca.service['task_id']),tenant_id=ca.creds['tenantId'],
				data=None,token=ca.creds['token'],method="GET")

	ca.log("Loaded current config.")
	data = json.loads(response)
	config = json.loads(data['config'])
	create = {
		"name": data['name'],
		"config": data['config'],
		"agent_url": data['agent_url'],
		"email": data['email'],
		"interval": "0",
		"start_at": "+"+str(config['interval'])
	}

	ca.log("Requesting new task.")
	response = agent_query(url=ca.service['api_url'],
				path="/tasks",tenant_id=ca.creds['tenantId'],
				data=json.dumps(create),token=ca.creds['token'],method="POST")
	next = json.loads(response)

	ca.log("Next Agent: "+str(next['task_id']))
	


def agent_query(**args):
	'''
	Make a query to the Agent API Service
	
	token = keystone token
	url = agent API url
	tenant_id = Tenant
	
	path = request to make
	data = post data
	'''

	if not args['url'][-1] == "/":
		args['url'] = args['url']+"/v1.0/"
	
	url = args['url']+"v1.0/tenants/"+args['tenant_id']

	
	if args['data']:
		if args['data'][0] == '<':
			contenttype = "application/xml"
		elif args['data'][0] == '{':
			contenttype = "application/json"
		else:
			contenttype = "application/x-html-encoded"

	if args['data']:
		request = urllib2.Request(url+args['path'],
		args['data'], {'X-Auth-Token':args['token'],"Content-type":contenttype})
	else:
		request = urllib2.Request(url+args['path'],
		None, {'X-Auth-Token':args['token']})
	
	if args['method']:
		request.get_method = lambda: args['method']
	
	try:
		response = urllib2.urlopen(request)
	except urllib2.HTTPError, e:
		raise StandardError("HTTP Error from agent service: "+str(e))
	return response.read()


ca.run(agent)
