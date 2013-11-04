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
from base64 import b64encode, b64decode
import json
from sqlalchemy import Table, Column, Integer, Boolean, Text, DateTime, String, MetaData
from sqlalchemy import ForeignKey, create_engine, UniqueConstraint, select, func, desc, asc
from sqlalchemy.sql import text
from sqlalchemy.exc import IntegrityError
import urllib2
from bottle import route, request, run, HTTPResponse
import re
from datetime import datetime, timedelta
from dateutil import parser
import ConfigParser
import pytz
import cgi
import sys
import os

@route('/')
def index():
	return "It's-a-pasta time!"
	
@route('/v1.0')
@route('/v1.0/')
def index():
	return "I'm the very model of a modern major general!"

# GET /v1.0/agents/ - List all known agents.
# GET /v1.0/agents/:agent_id - Show a specific agent.


# GET /v1.0/tenants/:tenant_id/accesskeys/ - List all accesskeys for a tenant.
# GET /v1.0/tenants/:tenant_id/accesskeys/:accesskey_id - Show a specific accesskey.
# POST /v1.0/tenants/:tenant_id/accesskeys/ - Create a accesskey entry for a tenant.
# PUT /v1.0/tenants/:tenant_id/accesskeys/:accesskey_id - Update a accesskey.
# DELETE /v1.0/tenants/:tenant_id/accesskeys/:accesskey_id - Delete a accesskey.

# POST /v1.0/tenants/:tenant_id/agent_config/
#	- Feed in agent location, returns agent config request id.
# GET /v1.0/tenants/:tenant_id/agent_config/:config_request_id
#	- Feed in agent config request id, returns configuration json.

# GET /v1.0/tenants/:tenant_id/tasks/ - List a tenants tasks.
# GET /v1.0/tenants/:tenant_id/tasks/:task_id - Show a specific task.
# POST /v1.0/tenants/:tenant_id/tasks/ - Create a new task.
# PUT /v1.0/tenants/:tenant_id/tasks/:task_id - Update a new task.
# DELETE /v1.0/tenants/:tenant_id/tasks/:task_id - Delete a task.

# GET /v1.0/tenants/:tenant_id/tasks/:task_id/runs/
#	- Returns a list of task runs, with the last message from each.
# GET /v1.0/tenants/:tenant_id/tasks/:task_id/runs/:task_run_id/messages/
#	- Get the output from a specific task run.
# GET /v1.0/tenants/:tenant_id/tasks/:task_id/runs/:task_run_id/messages/?since=:task_run_message_id
#	- Get the output from a specific task run since a specific message_id.


# --------------------------
#
# Agents!
#
# --------------------------

@route('/v1.0/agents', method='GET')
@route('/v1.0/agents/', method='GET')
def read_agents():
	"""
	Get a list of agents.
	"""
	json_results = []
	results = engine.execute(select([agents]).order_by(asc(agents.c.name)))
	for agent in results.fetchall():
		json_results.append({
			"id": agent.id,
			"name": agent.name,
			"version": agent.version,
			"author": agent.author,
			"help": agent.help,
			"url": agent.url,
			"agent_url": agent.agent_url,
			"links": [
				{"rel": "self",
				"href": site_url+"/v1.0/agents/"+str(agent.id)}
				]
			})
	return json.dumps({"agents": json_results})

@route('/v1.0/agents/:agent_id', method='GET')
def read_agent(agent_id='agent_id'):
	"""
	Get details for an agent.
	"""
	results = engine.execute(select([agents], agents.c.id==agent_id))
	if results.rowcount:
		agent = results.fetchone()
		json_results = {
			"id": agent.id,
			"name": agent.name,
			"version": agent.version,
			"author": agent.author,
			"url": agent.url,
			"agent_url": agent.agent_url,
			"help": agent.help,
			"config": agent.config,
			"links": [
				{"rel": "self",
				"href": site_url+"/v1.0/agents/"+str(agent.id)}
				]
			}
		
		return str(json.dumps({"agent": json_results}))
	else:
		raise HTTPResponse(output='Agent not found.', status=404, header=None)
		

# --------------------------
#
# Tasks!
#
# --------------------------


@route('/v1.0/tenants/:tenant_id/tasks', method='GET')
@route('/v1.0/tenants/:tenant_id/tasks/', method='GET')
def read_tasks(tenant_id='tenant_id'):
	"""
	Get a list of tasks for a tenant.
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)

			
	json_results = []
	sql_query = text("""
		SELECT t.*,
		tr.id as task_run_id,
		tr.status as task_run_status,
		tr.started_at as task_run_started_at,
		tr.updated_at as task_run_updated_at,
		tr.failed_at as task_run_failed_at
		FROM tasks AS t
		LEFT JOIN task_runs AS tr ON (tr.task_id = t.id)
		WHERE tr.id = (
			SELECT MAX(id) FROM task_runs AS tr2
				WHERE tr2.task_id = t.id
		)
		AND t.tenant_id = :tenant_id
		AND (t.status = 'active' or t.status = 'finished' or
		t.status = 'running' or t.status = 'complete')
		ORDER BY t.id DESC
	""")
	results = engine.execute(sql_query, tenant_id=tenant_id)
	for result in results.fetchall():
		json_results.append({
			"id": result.id,
			"name": result.name,
			"agent_url": result.agent_url,
			"created_at": date_prep(result.created_at),
			"last_scheduled_at": date_prep(result.last_scheduled_at),
			"email": result.email,
			"status": result.status,
			"interval": result.interval,
			"latest_task_run": {
				"id": result.task_run_id,
				"status": result.task_run_status,
				"started_at": date_prep(result.task_run_started_at),
				"updated_at": date_prep(result.task_run_updated_at),
				"failed_at": date_prep(result.task_run_failed_at),
				"links": [
					{"rel": "self",
					"href": site_url+"/v1.0/tenants/"+tenant_id+"/tasks/"+str(result.id)+"/runs/"+ \
							str(result.task_run_id)},
					{"rel": "messages",
					"href": site_url+"/v1.0/tenants/"+tenant_id+"/tasks/"+str(result.id)+"/runs/"+ \
							str(result.task_run_id)+"/messages"}
					]
			},
			"links": [
				{"rel": "self",
				"href": site_url+"/v1.0/tenants/"+tenant_id+"/tasks/"+str(result.id)}
				]
		})
	return str(json.dumps({"tasks": json_results}, sort_keys=True, indent=4))

@route('/v1.0/tenants/:tenant_id/tasks/:task_id', method='GET')
def read_task(tenant_id='tenant_id',task_id='task_id'):
	"""
	Get the details of a task.
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)


			
	json_results = []
	sql_query = text("""
		SELECT t.*,
		tr.id as task_run_id,
		tr.status as task_run_status,
		tr.started_at as task_run_started_at,
		tr.updated_at as task_run_updated_at,
		tr.failed_at as task_run_failed_at
		FROM tasks AS t
		LEFT JOIN task_runs AS tr ON (tr.task_id = t.id)
		WHERE tr.id = (
			SELECT MAX(id) FROM task_runs AS tr2
				WHERE tr2.task_id = t.id
		)
		AND t.tenant_id = :tenant_id
		AND t.id = :task_id
		ORDER BY t.id DESC
	""")
	results = engine.execute(sql_query, tenant_id=tenant_id, task_id=task_id)
	result = results.fetchone()
	
	if result:
		crypted = decrypt_dict(tenant_id,{"config": result.config})
	
		json_results= {
			"id": result.id,
			"name": result.name,
			"config": crypted['config'],
			"agent_url": result.agent_url,
			"email": result.email,
			"created_at": date_prep(result.created_at),
			"last_scheduled_at": date_prep(result.last_scheduled_at),
			"interval": result.interval,
			"status": result.status,
			"latest_task_run": {
				"id": result.task_run_id,
				"status": result.task_run_status,
				"started_at": date_prep(result.task_run_started_at),
				"updated_at": date_prep(result.task_run_updated_at),
				"failed_at": date_prep(result.task_run_failed_at),
				"links": [
					{"rel": "self",
					"href": site_url+"/v1.0/tenants/"+tenant_id+"/tasks/"+str(result.id)+"/runs/"+ \
							str(result.task_run_id)},
					{"rel": "messages",
					"href": site_url+"/v1.0/tenants/"+tenant_id+"/tasks/"+str(result.id)+"/runs/"+ \
							str(result.task_run_id)+"/messages"}
					]
			},
			"links": [
				{"rel": "self",
				"href": site_url+"/v1.0/tenants/"+tenant_id+"/tasks/"+str(result.id)}
				]
		}
		return str(json.dumps(json_results, sort_keys=True, indent=4))
	else:
		raise HTTPResponse(output='Task not found.', status=404, header=None)

@route('/v1.0/tenants/:tenant_id/tasks', method='POST')
@route('/v1.0/tenants/:tenant_id/tasks/', method='POST')
def create_task(tenant_id='tenant_id'):
	"""
	Create a new task entry.
	POST format:
	{
		"name": "My New Task",
		"config": "\{\"task\": \"do something\"\}",
		"agent_url": "swift://region-a.geo-1/mycontainer/myagent.py",
		"email": "jeff.kramer@hp.com",
		"interval": "300",
		"start_at": "0"
	}
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)


	
	post = json.loads(request.body.read())
	validation = {
		'name' : "^[\w\:\_\ \!\.]{3,80}$",
		'config' : "^.*$",
		'agent_url' : "^\w{3,5}\:\/\/[\w\-\.]{0,40}\/.{1,80}\.\w{1,5}$",
		'interval' : "^\d+$",
		'email' : "^.+$",
		'start_at' : "^[\w\ \:\+\.\-]{1,50}$"
	}

	if not validate_dict(post, validation):
		raise HTTPResponse(output="Validation error, input JSON didn't match required format: " \
				+str(validation), status=400, header=None)
	
	start_at = post['start_at']
	crypted = encrypt_dict(tenant_id,{"config": post['config']})

	if start_at == '0':
	
		result = engine.execute(tasks.insert(),
			name=post['name'],
			config=crypted['config'],
			agent_url=post['agent_url'],
			email=post['email'],
			interval=post['interval'],
			start_at=func.now(),
			last_scheduled_at=func.now(),
			status="active",
			tenant_id=tenant_id)
	else:
		if start_at[0] == '+':
			try:
				secs_from_now = int(start_at[1::])
			except ValueError:
				raise HTTPResponse(status=400, header=None,
						output="Error with start_at format, format: +[secs in future]!")
			start_at = (datetime.now() + timedelta(seconds=secs_from_now)).isoformat()
	
		result = engine.execute(tasks.insert(),
			name=post['name'],
			config=crypted['config'],
			agent_url=post['agent_url'],
			email=post['email'],
			interval=post['interval'],
			status="active",
			start_at=start_at,
			last_scheduled_at=start_at,
			tenant_id=tenant_id)
	
	if result:
		task_id = result.lastrowid
	else:
		raise HTTPResponse(output='Error adding task.', status=500, header=None)

	task_run_id = create_task_run(task_id)
	
	if task_run_id:
		return json.dumps({"message": "Task created!","task_id":task_id,"task_run_id":task_run_id})
	else:
		raise HTTPResponse(output='Error adding task.', status=500, header=None)


@route('/v1.0/tenants/:tenant_id/tasks/:task_id', method='PUT')
def update_task(tenant_id='tenant_id',task_id='task_id'):
	"""
	Update a task entry.
	PUT format:
	{
		"name": "My New Task",
		"config": "\{\"task\": \"do something\"\}",
		"agent_url": "swift://region-a.geo-1/mycontainer/myagent.py",
		"email": "jeff.kramer@hp.com",
		"interval": 300,
		"start_at": 0
	}
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)


	
	post = json.loads(request.body.read())
	validation = {
		'name' : "^[\w\:\_\ \!\.]{3,80}$",
		'config' : "^.*$",
		'agent_url' : "^\w{3,5}\:\/\/[\w\-\.]{1,40}\/.{1,80}\.\w{1,5}$",
		'email' : "^.+$",
		'interval' : "^\d+$",
		'start_at' : "^[\w\ \:\+\.\-]{1,50}$"
	}

	if not validate_dict(post, validation):
		raise HTTPResponse(output="Validation error, input JSON didn't match required format: " \
				+str(validation), status=400, header=None)
	
	start_at = post['start_at']

	crypted = encrypt_dict(tenant_id,{"config": post['config']})
	if start_at == '0':
		result = engine.execute(tasks.update().where(tasks.c.id==task_id).
		where(tasks.c.tenant_id==tenant_id).where(tasks.c.status=='active').values(
			name=post['name'],
			config=crypted['config'],
			agent_url=post['agent_url'],
			email=post['email'],
			last_scheduled_at=0,
			interval=post['interval'],
			start_at=func.now(),
			tenant_id=tenant_id))
	else:
		if start_at[0] == '+':
			try:
				secs_from_now = int(start_at[1::])
			except ValueError:
				raise HTTPResponse(output="start_at invalid, format: +[secs in future]!",
									status=400, header=None)
			start_at = (datetime.now() + timedelta(seconds=secs_from_now)).isoformat()
	
		result = engine.execute(tasks.update().
								where(tasks.c.id==task_id).
								where(tasks.c.tenant_id==tenant_id).
								where(tasks.c.status=='active').
								values(
									name=post['name'],
									config=crypted['config'],
									agent_url=post['agent_url'],
									last_scheduled_at=0,
									email=post['email'],
									interval=post['interval'],
									start_at=start_at,
									tenant_id=tenant_id))
			
	if result.rowcount: 
		return json.dumps({
					"message": "Task updated!",
					"task_id": task_id,
					"links": [
						{"rel": "self",
						"href": site_url+"/v1.0/tenants/"+tenant_id+"/tasks/"+str(task_id)}
						]
					})
	else:
		raise HTTPResponse(output='Error updating task.', status=500, header=None)
	


@route('/v1.0/tenants/:tenant_id/tasks/:task_id', method='DELETE')
def delete_task(tenant_id='tenant_id',task_id='task_id'):
	"""
	Set a task to deleted.  You can only delete 'active' tasks.
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)


			
	json_results = []
	results = engine.execute(tasks.update().
								where(tasks.c.tenant_id==tenant_id).
								where(tasks.c.id == task_id).
								where(tasks.c.status == 'active').
								values(status='deleted'))
	if results.rowcount:
		raise HTTPResponse(output='', status=204, header=None)
	else:
		raise HTTPResponse(output='Task not found.', status=404, header=None)




# --------------------------
#
# Task Runs!
#
# --------------------------

@route('/v1.0/tenants/:tenant_id/tasks/:task_id/runs', method='GET')
@route('/v1.0/tenants/:tenant_id/tasks/:task_id/runs/', method='GET')
def read_tasks(tenant_id='tenant_id',task_id="task_id"):
	"""
	Get a list of task runs for a task.
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)
			
	json_results = []
	sql_query = text("""
		select tr.*
		from task_runs as tr, tasks as t
		where tr.task_id = :task_id
		and t.tenant_id = :tenant_id
		and tr.task_id = t.id
		order by tr.id desc
		limit 20
	""")
	results = engine.execute(sql_query, tenant_id=tenant_id, task_id=task_id)
	for result in results.fetchall():
		json_results.append({
			"id": result.id,
			"status": result.status,
			"started_at": date_prep(result.started_at),
			"updated_at": date_prep(result.updated_at),
			"failed_at": date_prep(result.failed_at),
		})
	return str(json.dumps({"task_runs": json_results}, sort_keys=True, indent=4))

@route('/v1.0/tenants/:tenant_id/tasks/:task_id/runs/:task_run_id/messages', method='GET')
@route('/v1.0/tenants/:tenant_id/tasks/:task_id/runs/:task_run_id/messages/', method='GET')
def read_task_messages(tenant_id='tenant_id',task_id="task_id",task_run_id="task_run_id"):
	"""
	Get the details of a specific task run.
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)



	sql_query = text("""
		select tr.*
		from task_runs as tr, tasks as t
		where tr.task_id = :task_id
		and t.tenant_id = :tenant_id
		and tr.id = :task_run_id
		and tr.task_id = t.id
	""")
	results = engine.execute(sql_query, tenant_id=tenant_id, task_id=task_id,
							task_run_id=task_run_id)
	if results.rowcount:
		result = results.fetchone()
		json_results = {
			"id": result.id,
			"status": result.status,
			"started_at": date_prep(result.started_at),
			"updated_at": date_prep(result.updated_at),
			"failed_at": date_prep(result.failed_at),
			"messages": []
		}
		
		if request.query.get('since'):
		
			task_run_message_id = int(request.query.get('since'))
			sub_results = engine.execute(select([task_run_messages], 
				task_run_messages.c.task_run_id==result.id).
				where(task_run_messages.c.id > task_run_message_id).
				where(task_run_messages.c.type != 'sys').
				order_by(asc(task_run_messages.c.id)))
		
		else:
		
			sub_results = engine.execute(select([task_run_messages], 
				task_run_messages.c.task_run_id==result.id).
				where(task_run_messages.c.type=='note').
				order_by(asc(task_run_messages.c.id)))

		for sub_result in sub_results.fetchall():
			json_results['messages'].append({
				"id":  sub_result.id,
				"title": cgi.escape(sub_result.title),
				"message": cgi.escape(sub_result.message),
				"type": sub_result.type,
				"percent": sub_result.percent,
				"created_at": date_prep(sub_result.created_at)
			})
		return str(json.dumps(json_results, sort_keys=True, indent=4))

	else:
		raise HTTPResponse(output='Task not found.', status=404, header=None)

@route('/v1.0/tenants/:tenant_id/tasks/:task_id/runs/:task_run_id/stream', method='GET')
@route('/v1.0/tenants/:tenant_id/tasks/:task_id/runs/:task_run_id/stream/', method='GET')
def read_task_message_stream(tenant_id='tenant_id',task_id="task_id",task_run_id="task_run_id"):
	"""
	Read the messages from a specific task until it's finished.
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)

	sql_query = text("""
		select tr.*
		from task_runs as tr, tasks as t
		where tr.task_id = :task_id
		and t.tenant_id = :tenant_id
		and tr.id = :task_run_id
		and tr.task_id = t.id
	""")
	results = engine.execute(sql_query, tenant_id=tenant_id, task_id=task_id,
							task_run_id=task_run_id)

	if results.rowcount:
	
		last_message_id = 0
		if request.query.get('since'):
			task_run_message_id = int(request.query.get('since'))
			sub_results = engine.execute(select([task_run_messages], 
				task_run_messages.c.task_run_id==task_run_id).
				where(task_run_messages.c.id > task_run_message_id).
				where(task_run_messages.c.type != 'sys').
				order_by(asc(task_run_messages.c.id)))
		
		else:
			sub_results = engine.execute(select([task_run_messages], 
				task_run_messages.c.task_run_id==task_run_id).
				where(task_run_messages.c.type=='note').
				order_by(asc(task_run_messages.c.id)))
		
		
		for sub_result in sub_results.fetchall():
			yield json.dumps({
				"id":  sub_result.id,
				"title": cgi.escape(sub_result.title),
				"message": cgi.escape(sub_result.message),
				"type": sub_result.type,
				"percent": sub_result.percent,
				"created_at": date_prep(sub_result.created_at)
			})+"\n"
			last_message_id = sub_result.id

		while True:
			sub_results = engine.execute(select([task_run_messages], 
				task_run_messages.c.task_run_id==task_run_id).
				where(task_run_messages.c.type=='note').
				where(task_run_messages.c.id>last_message_id).
				order_by(asc(task_run_messages.c.id)))
			if sub_results.rowcount:
				for sub_result in sub_results.fetchall():
					yield json.dumps({
						"id":  sub_result.id,
						"title": cgi.escape(sub_result.title),
						"message": cgi.escape(sub_result.message),
						"type": sub_result.type,
						"percent": sub_result.percent,
						"created_at": date_prep(sub_result.created_at)
					})+"\n"
					last_message_id = sub_result.id
			run_check = engine.execute(select([task_runs], task_runs.c.id == task_run_id))
			check = run_check.fetchone()
			if check.status == "succeeded" or check.status == "failed":
				return
			
			sleep(0)

		return

	else:
		raise HTTPResponse(output='Task not found.', status=404, header=None)


# --------------------------
#
# Access Keys!
#
# --------------------------

@route('/v1.0/tenants/:tenant_id/accesskeys', method='GET')
@route('/v1.0/tenants/:tenant_id/accesskeys/', method='GET')
def read_accesskeys(tenant_id='tenant_id'):
	"""
	Get a list of accesskeys for a tenant. (Access Key only.)
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)


			
	json_results = []
	results = engine.execute(select([accesskeys.c.id, accesskeys.c.accessKey], 
		accesskeys.c.tenant_id==tenant_id))
	decrypt = {}
	for result in results.fetchall():
		decrypt[str(result[0])] = result[1]
	decrypted = decrypt_dict(tenant_id,decrypt)
	for id,accesskey in decrypted.items():
		json_results.append({"id": int(id), "accessKey": accesskey})
	return json.dumps({"accesskeys": json_results})

@route('/v1.0/tenants/:tenant_id/accesskeys/:accesskey_id', method='GET')
def read_accesskey(tenant_id='tenant_id',accesskey_id='accesskey_id'):
	"""
	Get accesskeys for a tenant. (Access Key only.)
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)


			
	json_results = []
	results = engine.execute(select([accesskeys.c.id, accesskeys.c.accessKey], 
		accesskeys.c.tenant_id==tenant_id).where(accesskeys.c.id == int(accesskey_id)))
	for result in results.fetchall():
		decrypt[str(result[0])] = result[1]
	decrypted = decrypt_dict(tenant_id,decrypt)
	for id,accesskey in decrypted.items():
		json_results.append({"id": int(id), "accessKey": accesskey})
	return json.dumps({"accesskeys": json_results})

@route('/v1.0/tenants/:tenant_id/accesskeys/:accesskey_id', method='DELETE')
def delete_accesskey(tenant_id='tenant_id',accesskey_id='accesskey_id'):
	"""
	Remove a accesskey from a tenant. (Access Key only.)
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)


			
	json_results = []
	results = engine.execute(accesskeys.delete().
							where(accesskeys.c.tenant_id==tenant_id).
							where(accesskeys.c.id == accesskey_id))
	if results.rowcount:
		raise HTTPResponse(output='', status=204, header=None)
	else:
		raise HTTPResponse(output='Accesskey not found.', status=404, header=None)
	

@route('/v1.0/tenants/:tenant_id/accesskeys', method='POST')
@route('/v1.0/tenants/:tenant_id/accesskeys/', method='POST')
def create_accesskey(tenant_id='tenant_id'):
	"""
	Create a new tenant accesskey entry.
	POST format:
	{
		"apiAccessKeyCredentials":{
			"accessKey":"19N488ACAF3859DW9AFS9",
			"secretKey":"vpGCFNzFZ8BMP1g8r3J6Cy7/ACOQUYyS9mXJDlxc"
		}
	}
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)

	post = json.loads(request.body.read())
	validation = {
		'apiAccessKeyCredentials' : {
				'accessKey' : "^[\w\:]+$",
				'secretKey' : "^\w+$"
		}
	}

	if not validate_dict(post, validation):
		raise HTTPResponse(output="Validation error, input JSON didn't match required format: " \
				+str(validation), status=400, header=None)
		
	if not cs_key_check(accesskey=post['apiAccessKeyCredentials']['accessKey'],
		secretkey=post['apiAccessKeyCredentials']['secretKey'],
		identity_url=identity_url, tenant_id=tenant_id):
		raise HTTPResponse(output="Keys don't authenticate.", status=401, header=None)
	try:
		crypted = encrypt_dict(tenant_id,{"accessKey": post['apiAccessKeyCredentials']['accessKey'],
									 "secretKey": post['apiAccessKeyCredentials']['secretKey']})

		result = engine.execute(accesskeys.insert(),
			accessKey=crypted['accessKey'],
			secretKey=crypted['secretKey'],
			tenant_id=tenant_id)
	except IntegrityError:
		raise HTTPResponse(output='Error adding accesskey.', status=500, header=None)
	return json.dumps({
				"message": "Accesskey created!",
				"accesskey_id": result.lastrowid,
				"links": [
						{"rel": "self",
						"href": site_url+"/v1.0/tenants/"+tenant_id+"/accesskeys/"+str(result.lastrowid)}
						]
				})

@route('/v1.0/tenants/:tenant_id/accesskeys/:accesskey_id', method='PUT')
def update_accesskey(tenant_id='tenant_id',accesskey_id='accesskey_id'):
	"""
	Update an existing accesskey.
	PUT format:
	{
		"apiAccessKeyCredentials":{
			"accessKey":"19N488ACAF3859DW9AFS9",
			"secretKey":"vpGCFNzFZ8BMP1g8r3J6Cy7/ACOQUYyS9mXJDlxc"
		}
	}
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)


	
	post = json.loads(request.body.read())
	validation = {
		'apiAccessKeyCredentials' : {
				'accessKey' : "^[\w\:]+$",
				'secretKey' : "^\w+$"
		}
	}

	if not validate_dict(post, validation):
		return "Validation error, input JSON didn't match required format: " + str(validation)
		
	if not cs_key_check(accesskey=post['apiAccessKeyCredentials']['accessKey'],
		secretkey=post['apiAccessKeyCredentials']['secretKey'],
		identity_url=identity_url, tenant_id=tenant_id):
		raise HTTPResponse(output="Keys don't authenticate.", status=401, header=None)
	
		crypted = encrypt_dict(tenant_id,{"accessKey": post['apiAccessKeyCredentials']['accessKey'],
									 "secretKey": post['apiAccessKeyCredentials']['secretKey']})

	result = engine.execute(accesskeys.update().values(
		accessKey=crypted['accessKey'],
		secretKey=crypted['secretKey']).
		where(accesskeys.c.id==int(accesskey_id)).
		where(accesskeys.c.tenant_id==tenant_id))
	if results.rowcount:
		return json.dumps({
					"message": "Accesskey updated!",
					"accesskey_id": int(accesskey_id),
					"links": [
							{"rel": "self",
							"href": site_url+"/v1.0/tenants/"+tenant_id+"/accesskeys/"+str(accesskey_id)}
							]
					})

	else:
		raise HTTPResponse(output="Error updating accesskey.", status=500, header=None)

# --------------------------
#
# Config Requests!
#
# --------------------------


@route('/v1.0/tenants/:tenant_id/agent_config', method='POST')
@route('/v1.0/tenants/:tenant_id/agent_config/', method='POST')
def add_config_request(tenant_id='tenant_id'):
	"""
	Request the configuration for an agent.
	POST format:
	{
		"agent_url": "swift://region-a.geo-1/mycontainer/myagent.py",
	}
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)
	
	post = json.loads(request.body.read())
	validation = {
		'agent_url' : "^\w{3,5}\:\/\/[\w\-\.]{0,40}\/.{1,80}\.\w{1,5}$",
	}

	if not validate_dict(post, validation):
		raise HTTPResponse(output="Validation error, input JSON didn't match required format: " \
				+str(validation), status=400, header=None)
	
	result = engine.execute(config_requests.insert(),
		agent_url=post['agent_url'],
		status="queued",
		tenant_id=tenant_id)

	if result:
		config_request_id = result.lastrowid
	else:
		raise HTTPResponse(output="Error adding config request.", status=500, header=None)

	return json.dumps({
				"message": "Config request added.",
				"config_request_id": int(config_request_id),
				"links": [
						{"rel": "self",
						"href": site_url+"/v1.0/tenants/"+tenant_id+"/agent_config/"+str(config_request_id)}
						]
				})

@route('/v1.0/tenants/:tenant_id/agent_config/:config_request_id', method='GET')
@route('/v1.0/tenants/:tenant_id/agent_config/:config_request_id/', method='GET')
def get_config_request(tenant_id='tenant_id', config_request_id='config_request_id'):
	"""
	Retrieve the configuration for an agent.
	"""
	if not identity_check(request,tenant_id):
		raise HTTPResponse(output='Identity invalid.', status=401, header=None)


	results = engine.execute(select([config_requests], 
		config_requests.c.tenant_id==tenant_id).where(config_requests.c.id == int(config_request_id)))
	
	result = results.fetchone()

	if result:
		if result.status == "queued" or result.status == "running":
			raise HTTPResponse(status=408, header=None)
		elif result.status == "failed":
			raise HTTPResponse(output="Agent config request failed.", status=406, header=None)
		else:
			print result.status, result.config
			return result.config

	else:
		raise HTTPResponse(output="Config request not found.", status=404, header=None)


# --------------------------
#
# Utility Functions!
#
# --------------------------


def date_prep(date):
	"""
	This function cleans up a datetime response object for insertion into JSON.
	"""
	response = str(date)
	if response == "None":
		return None
	else:
		return response

def identity_check(request,tenant_id):
	"""
	Pass our token and tenant ID to keystone for validation.
	This isn't a great long-term solution, but short term it validates
	that a customer has a real account.
	"""
	
	
	if request.headers.get("X-Auth-Token"):
		token = request.headers.get("X-Auth-Token")

		if auth_cache:
			if check_auth_cache(token,tenant_id):
				return True

		identity_request_json = json.dumps({
			'auth' : {
				'token' : {
					'id' : token,
				},
				"tenantId": tenant_id
			}
		})
		identity_req = urllib2.Request(identity_url+"/tokens",
		identity_request_json, {'Content-type':'application/json'})
		try:
			response = urllib2.urlopen(identity_req).read()
		except urllib2.HTTPError, e:
			return False
		response_json = json.loads(response)
		if response_json['access']['token']['tenant']['id'] == tenant_id:
			if auth_cache:
				add_auth_cache(token, tenant_id, response_json['access']['token']['expires'])
			return True
	return False


def check_auth_cache(token, tenant_id):
	"""
	Check to see if we have an entry for a token and tenant_id where now is less than the
	expiration time.
	"""
	if auth_cache_store.get(token+"/"+tenant_id):
			utc=pytz.UTC
			now = utc.localize(datetime.now())
			if now < auth_cache_store[token+"/"+tenant_id]:
				return True
			else:
				del auth_cache_store[token+"/"+tenant_id]
	return False

def add_auth_cache(token, tenant_id, expiration):
	"""
	Add an entry to our auth cache store.
	"""
	print "Adding cache entry"
	auth_cache_store[token+"/"+tenant_id] = parser.parse(expiration)


def cs_key_check(accesskey="",secretkey="",identity_url="",tenant_id=""):
	"""
	Pass our accesskey and secretkey to keystone for validation.
	This isn't a great long-term solution, but short term it validates
	that a key is real.
	"""
	
	identity_request_json = json.dumps({
		'auth' : {
			'apiAccessKeyCredentials' : {
				'accessKey' : accesskey,
				'secretKey' : secretkey
			},
			"tenantId": tenant_id
		}
	})
	identity_req = urllib2.Request(identity_url+"/tokens",
	identity_request_json, {'Content-type':'application/json'})
	try:
		response = urllib2.urlopen(identity_req).read()
	except urllib2.HTTPError, e:
		return False
	response_json = json.loads(response)
	if response_json['access']['token']['tenant']['id'] == tenant_id:
		return True
	return False

def validate_dict(input,validate):
	"""
	This function returns true or false if the dictionaries pass regexp
	validation.
	
	Validate format:
	
	{
	keyname: {
		substrname: "^\w{5,10}$",
		subintname: "^[0-9]+$"
		}
	}
	
	Validates that keyname exists, and that it contains a substrname
	that is 5-10 word characters, and that it contains subintname which
	is only integers.
	"""
	
	# Create a local copy to work our magic on.
	input = dict(input)
	
	if not type(input) == dict and type(validate) == dict:
		raise ValueError, "Values to validate_dict must be dicts."

	for key in validate.keys():
		if not input.get(key):
			# Key didn't exist.
			return False
		else:
			if not type(input[key]) == type(validate[key]) and not type(input[key]) == unicode:
				# The types of keys didn't match.
				return False
			elif type(input[key]) == dict:
				if not validate_dict(input[key],validate[key]):
					# The sub-validate didn't pass.
					return False
				else:
					del input[key]
			elif type(input[key]) == str or type(input[key]) == unicode:
				if not validate_str(input[key],validate[key]):
					# The sub-validate didn't pass.
					return False
				else:
					del input[key]
			elif type(input[key]) == int:
				del input[key]
				pass
			elif type(input[key]) == float:
				del input[key]
				pass
			else:
				# I don't know how to deal with this case!
				return False
	if input == {}:
		return True
	else:
		return False
			

def encrypt_dict(tenant_id,input):
	"""
	Encrypt a dictionary passed in to us, based on whatever our crypt_method
	option is set to.  Dictionary should be a 1 dimensional dict of strings, ie:
	{"tom": "cat", "jerry": "mouse"}
	"""
	output = {}
	if crypt_method == 'base64':
		for (identifier, message) in input.items():
			output[identifier] = b64encode(message)
			
	elif crypt_method == 'server':
		crypt_req = urllib2.Request(crypt_url+"/v1.0/tenants/"+tenant_id+"/encrypt",
									json.dumps({"values":input}),
									{'Content-type':'application/json'})
		try:
			response = urllib2.urlopen(crypt_req).read()
		except urllib2.HTTPError, e:
			print "error",e
			raise StandardError
		output = json.loads(response)['values']
		
	return output


def decrypt_dict(tenant_id,input):
	"""
	Decrypt a dictionary passed in to us.  Base64 values will be decoded locally,
	others will be passed to our crypt server.
	"""
	output = {}
	values = {}
	for (identifier, message) in input.items():
		junk,crypt_type,junk = message.split("-",3)
		if crypt_type == 'base64':
			output[identifier] = b64decode(message)
		else:
			values[identifier] = message
	
	if values:
		crypt_req = urllib2.Request(crypt_url+"/v1.0/tenants/"+tenant_id+"/decrypt",
									json.dumps({"values":values}),
									{'Content-type':'application/json'})
		try:
			response = urllib2.urlopen(crypt_req).read()
		except urllib2.HTTPError, e:
			raise StandardError
		output = dict(output.items() + json.loads(response)['values'].items())
		
	return output


def create_task_run(task_id):
	result = engine.execute(task_runs.insert(),
		task_id=task_id,
		status="queued"
	)

	if result:
		return result.lastrowid
	else:
		return False
	

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


if __name__ == "__main__":

	config = ConfigParser.RawConfigParser()
	config.read('ca.cfg')

	identity_url = config.get('API','identity_url')
	db_host = config.get('API','db_host')
	db_user = config.get('API','db_user')
	db_pass = config.get('API','db_pass')
	db_name = config.get('API','db_name')
	bind_address = config.get('API','bind_address')
	bind_port = config.get('API','bind_port')
	site_url = config.get('API','site_url')
	crypt_url = config.get('API','crypt_url')
	crypt_method = config.get('API','crypt_method')
	auth_cache = config.getboolean('API','auth_cache')
	
	auth_cache_store = {}
	
	engine = create_engine('mysql://%s:%s@%s/%s?charset=utf8' % (db_user, db_pass, db_host, db_name), pool_recycle=3600)

	metadata = MetaData()
	accesskeys = Table('accesskeys', metadata,
		Column('id', Integer, primary_key=True),
		Column('accessKey', String(200)),
		Column('secretKey', String(200)),
		Column('tenant_id', String(100), index=True),
		UniqueConstraint('accessKey', 'tenant_id', name="tenantkeys"),
		mysql_charset='utf8'
	)

	agents = Table('agents', metadata,
		Column('id', Integer, primary_key=True),
		Column('name', String(255)),
		Column('author', String(255)),
		Column('version', String(255)),
		Column('url', String(255)),
		Column('help', Text),
		Column('config', Text),
		Column('agent_url', String(255)),
		mysql_charset='utf8'
	)

	tasks = Table('tasks', metadata,
		Column('id', Integer, primary_key=True),
		Column('name', String(255)),
		Column('config', Text),
		Column('agent_url', String(255)),
		Column('email', String(255)),
		Column('tenant_id', String(255), index=True),
		Column('created_at', DateTime, default=func.now()),
		Column('updated_at', DateTime, onupdate=func.now()),
		Column('last_scheduled_at', DateTime, default=0),
		Column('interval',Integer),
		Column('status',String(20), index=True),
		Column('start_at',DateTime),
		Column('datastore',Text),
		mysql_charset='utf8'
	)
	
	task_runs = Table('task_runs', metadata,
		Column('id', Integer, primary_key=True),
		Column('task_id', Integer, index=True),
		Column('status', String(255)),
		Column('started_at', DateTime),
		Column('updated_at', DateTime),
		Column('failed_at', DateTime),
		mysql_charset='utf8'
	)

	task_run_messages = Table('task_run_messages', metadata,
		Column('id', Integer, primary_key=True),
		Column('task_run_id', Integer, index=True),
		Column('title', Text),
		Column('message', Text),
		Column('type', String(255)),
		Column('status', String(255)),
		Column('percent', Integer),
		Column('created_at', DateTime, default=func.now()),
		mysql_charset='utf8'
	)

	config_requests = Table('config_requests', metadata,
		Column('id', Integer, primary_key=True),
		Column('agent_url', String(255)),
		Column('tenant_id', String(255), index=True),
		Column('config', Text),
		Column('status', String(255)),
		Column('created_at', DateTime, default=func.now()),
		mysql_charset='utf8'
	)



	# This won't overwrite if they already exist.
	metadata.create_all(engine)
	
	sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
	run(host=bind_address, port=bind_port, reloader=True, server="gevent")
