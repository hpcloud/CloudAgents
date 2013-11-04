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

from gevent import monkey, sleep; monkey.patch_all()
from gevent.pool import Group
import gevent
import json
import urllib2
from bottle import route, request, response, run, HTTPResponse, \
					template, redirect, static_file, debug
import re
import ConfigParser
import cgi
from time import sleep

import datetime
import iso8601

@route('/public/<filename:path>')
def send_static(filename):
    return static_file(filename, root='./public')


@route('/')
def index():
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	accesskeys = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/accesskeys",
							data='', method="GET"))
	tasks = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/tasks",
							data='', method="GET"))
	if not len(accesskeys['accesskeys']):
		redirect("/accesskeys")
	if not len(tasks['tasks']):
		redirect("/agents")
	else:
		redirect("/tasks")
	

@route('/accesskeys')
@route('/accesskeys/')
def accesskeys_index():
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	
	accesskeys = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/accesskeys",
							data='', method="GET"))
	warning = ''
	if not len(accesskeys['accesskeys']):
		warning = "You must first add an access key to use the Cloud Agents service."

	return template('templates/accesskeys_index',accesskeys=accesskeys['accesskeys'], warning=warning)

@route('/accesskeys', method="POST")
@route('/accesskeys/', method="POST")
def accesskeys_index():
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	error = None
	if request.forms.get('action') == 'POST':
		if not validate_str(request.forms.accesskey,"^.+$"):
			error="Access Key missing."
		if not validate_str(request.forms.secretkey,"^.+$"):
			error="Secret Key missing."
	
		if not error:
			accesskey_request_json = json.dumps({
				'apiAccessKeyCredentials' : {
					'accessKey' : request.forms.accesskey,
					'secretKey' : request.forms.secretkey
				}
			})
	
			try:
				response = json.loads(agent_query(token=token,url=api_url,
								path="/v1.0/tenants/"+tenant_id+"/accesskeys",
								data=accesskey_request_json, method="POST"))
			except StandardError, e:
				error = "Error adding access key: " + e[0]
	
	elif request.forms.get('action') == 'DELETE':
		if not validate_str(request.forms.id,"^\d+$"):
			error="ID invalid."
		print "Got here"
		if not error:
			try:
				print "attempting delete"
				response = agent_query(token=token,url=api_url,
								path="/v1.0/tenants/"+tenant_id+"/accesskeys/"+request.forms.id,
								data='', method="DELETE")
			except StandardError, e:
				error = "Error deleting access key: " + e[0]
	else:
		error = "Method unknown."

	if not error:
		redirect("/accesskeys")
	else:
		accesskeys = json.loads(agent_query(token=token,url=api_url,
								path="/v1.0/tenants/"+tenant_id+"/accesskeys",
								data='', method="GET"))
		return template('templates/accesskeys_index',accesskeys=accesskeys['accesskeys'], error=request.query.get('error'))



@route('/tasks')
@route('/tasks/')
def tasks_index():
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	
	tasks = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/tasks",
							data='', method="GET"))
	return template('templates/tasks_index',tasks=tasks['tasks'])

@route('/tasks/:task_id')
@route('/tasks/:task_id/')
def tasks_show(task_id='task_id'):
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	
	task = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/tasks/"+task_id,
							data='', method="GET"))
	task['pretty_config'] = cgi.escape(json.dumps(json.loads(task['config']), indent=4))
	task_runs = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/tasks/"+task_id+"/runs",
							data='', method="GET"))
	
	return template('templates/tasks_show',task=task, task_runs=task_runs['task_runs'])

@route('/tasks/:task_id/delete', method="POST")
@route('/tasks/:task_id/delete/', method="POST")
def task_delete(task_id='task_id'):
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	
	task = agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/tasks/"+task_id,
							data='', method="DELETE")

	redirect("/tasks/"+task_id)

@route('/tasks/:task_id/runs/:task_run_id')
@route('/tasks/:task_id/runs/:task_run_id/')
def tasks_show(task_id='task_id', task_run_id='task_run_id'):
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	task = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/tasks/"+task_id,
							data='', method="GET"))	
	#task_run = json.loads(agent_query(token=token,url=api_url,
	#						path="/v1.0/tenants/"+tenant_id+"/tasks/"+task_id+"/runs/"+task_run_id+"/messages",
	#						data='', method="GET"))	
	return template('templates/task_runs_show',task=task, task_run={"id": task_run_id})

@route('/tasks/:task_id/runs/:task_run_id/stream')
@route('/tasks/:task_id/runs/:task_run_id/stream/')
@route('/tasks/:task_id/runs/:task_run_id/stream',method="POST")
@route('/tasks/:task_id/runs/:task_run_id/stream/',method="POST")
def tasks_show_stream(task_id='task_id', task_run_id='task_run_id'):
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
		response.content_type = 'application/json; charset=utf-8'
		identity_req = urllib2.Request(api_url+"/v1.0/tenants/"+tenant_id+"/tasks/"+task_id+"/runs/"+task_run_id+"/stream", None, {'X-Auth-Token':token, 'Content-type':'application/json'})
		resp_obj = urllib2.urlopen(identity_req)
		resp_obj.fp._sock.recv(0)
		yield '{"messages": ['
		for response_line in iter(resp_obj.readline, ''):
			yield response_line+","
			
		yield '{}]}\n'

@route('/tasks/:task_id/runs/:task_run_id/since/:task_run_message_id')
@route('/tasks/:task_id/runs/:task_run_id/since/:task_run_message_id/')
def tasks_show_messages(task_id='task_id', task_run_id='task_run_id', task_run_message_id='task_run_message_id'):
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
		response.content_type = 'application/json; charset=utf-8'
		identity_req = urllib2.Request(api_url+"/v1.0/tenants/"+tenant_id+"/tasks/"+task_id+"/runs/"+task_run_id+"/messages?since="+task_run_message_id, None, {'X-Auth-Token':token, 'Content-type':'application/json'})
		resp_obj = urllib2.urlopen(identity_req)
		return resp_obj.read()

@route('/custom')
@route('/custom/')
def custom_index():
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	
	return template('templates/custom_index')

@route('/agents')
@route('/agents/')
def agents_index():
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	
	agents = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/agents", data='', method="GET"))
	return template('templates/agents_index',agents=agents['agents'])

@route('/agent/show', method="POST")
@route('/agent/show/', method="POST")
@route('/agent/show', method="GET")
@route('/agent/show/', method="GET")
def agent_show():
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	if request.method == "POST":
		url = request.forms.url
	else:
		url = request.query.url
	
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
			print "Got error "+str(e)
			continue
		agent = json.loads(response)

	if not agent:
		return template('templates/agent_error',agent={},
						error="Unable to retrieve agent config: "+e[0])

	agent['agent_url'] = url

	agent['options'] = agent['config']
	for option in agent['options']:
		if option.get('resource'):
			service_catalog = get_service_catalog(token,tenant_id)
			break
	group = Group()
	threads = []
	for i, option in enumerate(agent['options']):
		if option.get('resource'):
			threads.append([token,tenant_id,service_catalog,option.get('resource'),i])
		
	for task in group.imap(get_template_resource,threads):
			agent['options'][task[0]]['resource-select'] = task[1]
	
	return template('templates/agent_show',agent=agent)

@route('/agent/create', method="POST")
@route('/agent/create/', method="POST")
def agents_create_task():
	if not request.cookies.get("token") or not request.cookies.get("tenant_id"):
		redirect("/login")
	else:
		token = request.get_cookie("token")
		tenant_id = request.get_cookie("tenant_id")
	error = None
	config = {}
	for input in request.forms:
		if input[0:7] == 'config-':
			if request.forms.get(input) == "checkbox-true":
				config[input[7:]] = True
			else:
				config[input[7:]] = request.forms.get(input)
	create = {
		"name": request.forms.name,
		"agent_url": request.forms.agent_url,
		"email": request.forms.email,
		"interval": request.forms.interval,
		"start_at": request.forms.start_at,
		"config": json.dumps(config)
		}
	create_json = json.dumps(create)
	try:
		agent = json.loads(agent_query(token=token,url=api_url,
							path="/v1.0/tenants/"+tenant_id+"/tasks/",
							data=create_json, method="POST"))
	except StandardError, e:
		return template('templates/agent_error',agent=dict(),
						error="Unable to create task: "+e[0])

	if agent.get('task_id'):
		redirect("/tasks/"+str(agent.get('task_id'))+"/runs/"+str(agent.get('task_run_id')))
	else:
		return str(agent)



@route('/login')
@route('/login/')
def login():
	return template('templates/login')


@route('/logout')
@route('/logout/')
def login():
	response.set_cookie("token", '', path="/")
	response.set_cookie("tenant_id", '', path="/")
	redirect("/")

@route('/login', method='POST')
@route('/login/', method='POST')
def attempt_login():
	
	if not validate_str(request.forms.username,"^.+$"):
		return template('templates/login',error="Username missing.")
	if not validate_str(request.forms.password,"^.+$"):
		return template('templates/login',
						error="Password missing.",
						username=request.forms.username)
	if not validate_str(request.forms.tenantid,"^\d*$"):
		return template('templates/login',
						error="TenantID invalid.",
						username=request.forms.username)
	if not request.forms.tenantid:
		tenants = get_tenant_list(request.forms.username,request.forms.password,identity_url)
		if not tenants:
			return template('templates/login',error="Login invalid.",
					username=request.forms.username)
		if tenants.get('tenants'):
			if len(tenants.get('tenants')) == 1:
				#rescope_token_to_tenant(token,tenants[0]['id'])
				token, timeout = get_cs_token_for_tenant(request.forms.username,request.forms.password,tenants['tenants'][0]['id'],identity_url)
				if not token:
					return template('templates/login',error="Login invalid.",
					username=request.forms.username)
				response.set_cookie("token", token, path="/", expires=iso8601.parse_date(timeout))
				response.set_cookie("tenant_id", tenants['tenants'][0]['id'], path="/", expires=iso8601.parse_date(timeout))
				redirect("/")
			else:
				# Not going to implement yet, since most people only have
				# one tenant.
				return template('templates/login',error="Multi-tenant users unsupported.")
	else:
		token, timeout = get_cs_token_for_tenant(request.forms.username,request.forms.password,request.forms.tenantid,identity_url)
		if not token:
			return template('templates/login',error="Login invalid.",
						username=request.forms.username)
		response.set_cookie("token", token, path="/", expires=iso8601.parse_date(timeout))
		response.set_cookie("tenant_id", request.forms.tenantid, path="/", expires=iso8601.parse_date(timeout))
		redirect("/")
			
	return template('templates/login',error="Login invalid.")

# Utility functions.

def get_template_resource(my_array):
	"""
	Go out and grab a list of options from services to create a pretty select-based
	option list for known resource types.
	"""
	token,tenant_id,service_catalog,resource,i = my_array
	print "looking for",resource
	if resource == 'openstack.compute.endpoints.region':
		return i,get_endpoint_region_list(token,tenant_id,'compute',service_catalog)
	elif resource == 'openstack.object-store.endpoints.region':
		return i,get_endpoint_region_list(token,tenant_id,'object-store',service_catalog)
	elif resource == 'openstack.compute.[region].flavors':
		return i,get_all_nova_element_list(token,tenant_id,service_catalog,get_flavors_list)
	elif resource == 'openstack.compute.[region].keypairs':
		return i,get_all_nova_element_list(token,tenant_id,service_catalog,get_keypairs_list)
	elif resource == 'openstack.compute.[region].security-groups':
		return i,get_all_nova_element_list(token,tenant_id,service_catalog,get_security_groups_list)
	elif resource == 'openstack.compute.[region].servers':
		return i,get_all_nova_element_list(token,tenant_id,service_catalog,get_servers_list)
	elif resource == 'openstack.object-store.[region].containers':
		return i,get_all_swift_containers(token,tenant_id,service_catalog)
	else:
		return i,[]

def get_endpoint_region_list(token,tenant_id,service_name,service_catalog):
	"""
	Get a list of regions from the identity service for a token/tenant and service.
	"""
	list = []
	for service in service_catalog:
		if service['type'] == service_name:
			for endpoint in service.get('endpoints'):
				list.append({"name":endpoint.get('region'),"value":endpoint.get('region')})
	return list

def get_service_catalog(token,tenant_id):
	"""
	Return the service catalog.
	"""
	identity_request_json = json.dumps({
		'auth' : {
			'tenantId' : tenant_id,
			'token': {'id': token}
		}
	})
	identity_req = urllib2.Request(identity_url+"/tokens", identity_request_json, 
						{'Content-type':'application/json','X-Auth-Token': token})
	try:
		response = urllib2.urlopen(identity_req).read()
		return json.loads(response)['access']['serviceCatalog']
	except urllib2.HTTPError, e:
		return False
	return False

def get_all_swift_containers(token,tenant_id,service_catalog):
	"""
	Get a list of items from every compute service the user has access to.
	"""
	list = []
	threads = []
	subgroup = Group()
	for service in service_catalog:
		if service['type'] == 'object-store':
			for endpoint in service.get('endpoints'):
				threads.append((token,tenant_id,endpoint.get('region'),endpoint.get('publicURL')))
	
	print threads
	for task in subgroup.imap(get_swift_containers,threads):
			list.extend(task)
	print list
	return list

def get_swift_containers(arg_list):
	"""
	Get a list of containers for a specific object-store service.
	"""
	token,tenant_id,region,url = arg_list
	request = urllib2.Request(url,None, {'X-Auth-Token':token})
	try:
		response = urllib2.urlopen(request)
	except urllib2.HTTPError, e:
		return []
	file_list = response.read().splitlines()
	print file_list
	list = []
	list.append({"name":region,"value":""})
	for file in file_list:
		list.append({"name":file,"value":file})
	return list


def get_all_nova_element_list(token,tenant_id,service_catalog,sub_function):
	"""
	Get a list of items from every compute service the user has access to.
	"""
	list = []
	threads = []
	subgroup = Group()
	for service in service_catalog:
		if service['type'] == 'compute':
			for endpoint in service.get('endpoints'):
				threads.append((token,tenant_id,endpoint.get('region'),endpoint.get('publicURL')))
	
	for task in subgroup.imap(sub_function,threads):
			list.extend(task)
	print list
	return list
	
def get_flavors_list(arg_list):
	"""
	Get a list of flavors for a specific compute service.
	"""
	token,tenant_id,region,url = arg_list
	req = urllib2.Request(url+"/flavors", None, 
						{'Content-type':'application/json','X-Auth-Token': token})
	try:
		response = urllib2.urlopen(req).read()
	except urllib2.HTTPError, e:
		return []
	list = []
	list.append({"name":region,"value":""})
	response_json = json.loads(response)
	for flavor in response_json.get('flavors'):
		list.append({"name":flavor.get('name'),"value":flavor.get('name')})
	return list

def get_servers_list(arg_list):
	"""
	Get a list of servers for a specific compute service.
	"""
	token,tenant_id,region,url = arg_list
	req = urllib2.Request(url+"/servers", None, 
						{'Content-type':'application/json','X-Auth-Token': token})
	try:
		response = urllib2.urlopen(req).read()
	except urllib2.HTTPError, e:
		return []
	list = []
	list.append({"name":region,"value":""})
	response_json = json.loads(response)
	for server in response_json.get('servers'):
		list.append({"name":server.get('name'),"value":server.get('name')})
	return list
	
def get_keypairs_list(arg_list):
	"""
	Get a list of keypairs for a specific compute service.
	"""
	token,tenant_id,region,url = arg_list
	req = urllib2.Request(url+"/os-keypairs", None, 
						{'Content-type':'application/json','X-Auth-Token': token})
	try:
		response = urllib2.urlopen(req).read()
	except urllib2.HTTPError, e:
		return []
	list = []
	list.append({"name":region,"value":""})
	response_json = json.loads(response)
	for keypair in response_json.get('keypairs'):
		list.append({"name":keypair.get('keypair').get('name'),"value":keypair.get('keypair').get('name')})
	return list
	
def get_security_groups_list(arg_list):
	"""
	Get a list of security groups for a specific compute service.
	"""
	token,tenant_id,region,url = arg_list
	req = urllib2.Request(url+"/os-security-groups", None, 
						{'Content-type':'application/json','X-Auth-Token': token})
	try:
		response = urllib2.urlopen(req).read()
	except urllib2.HTTPError, e:
		return []
	list = []
	list.append({"name":region,"value":""})
	response_json = json.loads(response)
	for group in response_json.get('security_groups'):
		list.append({"name":group.get('name'),"value":group.get('name')})
	return list

def get_tenant_list(username="",password="",identity_url=""):
	"""
	Pass our username and password to keystone for validation.
	"""
	
	identity_request_json = json.dumps({
		'auth' : {
			'passwordCredentials' : {
				'username' : username,
				'password' : password
			}
		}
	})
	identity_req = urllib2.Request(identity_url+"/tokens",
	identity_request_json, {'Content-type':'application/json'})
	try:
		response = urllib2.urlopen(identity_req).read()
	except urllib2.HTTPError, e:
		return False
	response_json = json.loads(response)
	identity_req = urllib2.Request(identity_url+"/tenants", None, 
							{'Content-type':'application/json',
							'X-Auth-Token': response_json['access']['token']['id']})
	try:
		response = urllib2.urlopen(identity_req).read()
	except urllib2.HTTPError, e:
		return False
	response_json = json.loads(response)
	if response_json.get('tenants'):
		return response_json
	else:
		return []

def get_cs_token_for_tenant(username="",password="",tenant_id="",identity_url=""):
	"""
	Pass our username and password to keystone for validation.
	"""
	
	identity_request_json = json.dumps({
		'auth' : {
			'passwordCredentials' : {
				'username' : username,
				'password' : password
			},
			"tenantId": tenant_id
		}
	})
	identity_req = urllib2.Request(identity_url+"/tokens",
	identity_request_json, {'Content-type':'application/json'})
	try:
		response = urllib2.urlopen(identity_req).read()
	except urllib2.HTTPError, e:
		print "Identity service returned error: "+str(e)
		return False, False
	response_json = json.loads(response)
	if response_json.get('access'):
		return (response_json['access']['token']['id'],response_json['access']['token']['expires'])
	else:
		return False, False

def rescope_token_to_tenant(token,tenant_id):
	"""
	Rescope a token to a tenant so we can do something with it.
	"""
	identity_request_json = json.dumps({
		'auth' : {
			'tenantId' : tenant_id,
			'token': {'id': token}
		}
	})
	identity_req = urllib2.Request(identity_url+"/tokens", identity_request_json, 
						{'Content-type':'application/json', 'X-Auth-Token': token})
	try:
		response = urllib2.urlopen(identity_req).read()
	except urllib2.HTTPError, e:
		return False
	

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


def validate_str(input,validate):
	"""
	This function returns true or false if the strings pass regexp
	validation.
	
	Validate format:

	substrname: "^\w{5,10}$",

	Validates that the string matches the regexp.
	"""

	if not re.match(validate,input) == None:
		# If the validation returned something, return true.
		return True
	return False
	
# You can monkey patch this to use named sockets thusly:
# http://blog.tinbrain.net/blog/2010/sep/30/django-and-gevent/


if __name__ == "__main__":

	config = ConfigParser.RawConfigParser()
	config.read('ca-web.cfg')

	identity_url = config.get('web','identity_url')
	api_url = config.get('web','api_url')
	bind_address = config.get('web','bind_address')
	bind_port = config.get('web','bind_port')
	debug(True)

	
	run(host=bind_address, port=bind_port, reloader=True, server="gevent")
