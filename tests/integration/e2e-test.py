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

import json
import argparse
import urllib2
import os
import sys
import swiftclient
from keystoneclient.v2_0 import client
import random
import string
from time import sleep
import time


def get_keystone_token(**args):
	'''
	Gets a keystone token from a keystone identity service.
	'''
	if 'accesskey' in args and args['accesskey']:
		identity_request = {
			'auth' : {
				'apiAccessKeyCredentials' : {
					'accessKey' : args['accesskey'],
					'secretKey' : args['secretkey']
				},
				"tenantId": args['tenant_id']
			}
		}
	elif 'username' in args and args['username']:
		identity_request = {
			'auth' : {
				'passwordCredentials' : {
					'username' : args['username'],
					'password' : args['password']
				},
				"tenantId": args['tenant_id']
			}
		}
	else:
		raise StandardError('Need username or accesskey to request token.')
	identity_url = args['identity_url']
	
	if identity_url[-1] != '/':
		identity_url += '/'
	
	identity_request_json = json.dumps(identity_request)

	request = urllib2.Request(identity_url+'tokens',
		identity_request_json, {'Content-type':'application/json'})
	try:
		response = urllib2.urlopen(request).read()
	except urllib2.HTTPError, e:
		raise StandardError("HTTP Error from identity service: "+str(e))
		
	response_json = json.loads(response)
	
	return response_json['access']['token']['id']
	
def agent_query(**args):
	'''
	Make a query to the Agent API Service
	
	token = keystone token
	url = agent API url
	tenant_id = Tenant
	
	path = request to make
	data = post data
	'''

	if args['url'][-1] == "/":
		args['url'] = args['url'][0:-1]
	
	url = args['url']
	
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
	if args.get('raw') == True:
		print response.read()
		sys.exit()
	else:
		return response.read()

def do_cleanup_and_quit(public_url, container_name, token):

	print "Deleting agent: wringer.py"
	swiftclient.client.delete_object(public_url, container=container_name,
										token=token, name="wringer.py")

	print "Deleting: "+container_name

	swiftclient.delete_container(public_url,token,container_name)

	print "Done."
	exit()

if __name__ == '__main__':

	parser = argparse.ArgumentParser(
		formatter_class=argparse.RawDescriptionHelpFormatter,
		description='''
This script tests the agent service top to bottom.
It does the following things, in order:

	1. Creates a new randomly named container and uploads
	   an agent script to it.
	2. Calls the agents service to retrieve the configuration
	   of the agent.
	3. Adds a task for the agent with a randomly set
	   configuration.
	4. Watches the task run to ensure completion.
	5. Checks the output to ensure valid execution.
	6. Cleans up the container.

Environment variables:
	OS_USERNAME and OS_PASSWORD or OS_ACCESSKEY and
	OS_SECRETKEY must be set, as well as OS_TENANT_ID,
	OS_IDENTITY_URL and OS_AGENTS_URL.

''')
	parser.add_argument('-r',dest='run', action='store_true',
		help='run the test')
	args = parser.parse_args()

	if not args.run:
		print "Run with -h for help, or -r to execute."
		exit()

	if not os.getenv('OS_TENANT_ID'):
		sys.exit("OS_TENANT_ID must be set.")
	if not os.getenv('OS_AGENTS_URL'):
		sys.exit("OS_AGENTS_URL must be set.")
	if not os.getenv('OS_SWIFT_REGION'):
		sys.exit("OS_SWIFT_REGION must be set.")

	tenant_id = os.getenv('OS_TENANT_ID')
	api_url = os.getenv('OS_AGENTS_URL')

	token = get_keystone_token(username=os.getenv('OS_USERNAME'),
		password=os.getenv('OS_PASSWORD'),
		accesskey=os.getenv('OS_ACCESSKEY'),
		secretkey=os.getenv('OS_SECRETKEY'),
		tenant_id=os.getenv('OS_TENANT_ID'),
		identity_url=os.getenv('OS_IDENTITY_URL'))

	keystone = client.Client(token=token, tenant_id=os.getenv('OS_TENANT_ID'),
							auth_url=os.getenv('OS_IDENTITY_URL'))
	
	object_store_catalog = keystone.service_catalog.get_endpoints()['object-store']
		
	for endpoints in object_store_catalog:
		if endpoints['region'] == os.getenv('OS_SWIFT_REGION'):
			region_endpoint = endpoints
	
	if not region_endpoint:
		print "Failing, swift region not found in endpoint list."
		exit()

	# Upload our file
	
	container_name = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(10))

	print "Creating: "+container_name
	swiftclient.put_container(region_endpoint['publicURL'],token,container_name)

	agent_file = open("wringer.py")

	print "Uploading agent: wringer.py"
	swiftclient.client.put_object(region_endpoint['publicURL'], container=container_name,
									token=token, name="wringer.py", contents=agent_file.read())

	# Request the config

	url = "swift://%s/%s/%s" % (region_endpoint['region'], container_name, "wringer.py")
	print "URL: "+url
	print "Requesting agent config."
	agent_call = agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/agent_config/",
							data=json.dumps({"agent_url":url}), method="POST")

	agent_request = json.loads(agent_call)
	agent = False

	c = 0
	while not agent and c < 30:
		sleep(1)
		c += 1
		api_request = urllib2.Request(agent_request['links'][0]['href'],
										None, {'X-Auth-Token':token})
		try:
			api_response = urllib2.urlopen(api_request)
			response = api_response.read()
		except urllib2.HTTPError, e:
			print "Got error: "+str(e)
			continue
		agent = json.loads(response)

	if not agent:
		print "Failure: Couldn't parse config."
		do_cleanup_and_quit(region_endpoint['publicURL'],container_name,token)
	else:
		print "Got config from agent."

	# Queue a task

	print "Queuing task."
	config = {}
	config['count'] = "1"
	create = {
		"name": "Integration Test "+time.strftime("%Y%m%d%H%M%S"),
		"agent_url": url,
		"email": "jeff.kramer@hp.com",
		"interval": "0",
		"start_at": "0",
		"config": json.dumps(config)
		}
	create_json = json.dumps(create)
	try:
		agent = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/tasks/",
							data=create_json, method="POST"))
	except StandardError, e:
		print "Unable to create task: "+str(e)
		do_cleanup_and_quit(region_endpoint['publicURL'],container_name,token)

	task_id = agent['task_id']

	c = 0
	success = False
	while not success and c < 30:
		sleep(1)
		c += 1
		print "Requesting task status."
		task = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/tasks/"+str(task_id),
							data='', method="GET"))
		if task['status'] == "complete":
			success = True	
		
	if not success:
		print "Task failed:"
		print task
		do_cleanup_and_quit(region_endpoint['publicURL'],container_name,token)
	else:
		print "Task succeeded!"
	
	do_cleanup_and_quit(region_endpoint['publicURL'],container_name,token)






