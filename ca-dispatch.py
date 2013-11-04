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

# This script checks for agents that need to be run,
# spins them up and runs them.

from gevent import monkey, sleep; monkey.patch_all()
import gevent
from base64 import b64encode, b64decode
import json
from sqlalchemy import Table, Column, Integer, Text, DateTime, String, MetaData
from sqlalchemy import ForeignKey, create_engine, UniqueConstraint, select, func, desc, asc
from sqlalchemy.sql import text
from sqlalchemy.exc import IntegrityError
import urllib2
import re
from datetime import datetime, timedelta
from gevent.queue import PriorityQueue, Empty
import ConfigParser
import sendgrid
import socket
import signal
from time import gmtime, strftime

import smtplib
from email import encoders
from email.message import Message
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template
import base64
import mimetypes

import os
import sys


def worker(n):
	try:
		priority,task_run = gevent_tasks.get(timeout=1) # decrements queue size by 1
		log('Worker %s got task run %s at priority %s' % (n, task_run, priority))

		sub_engine = create_engine('mysql://%s:%s@%s/%s?charset=utf8' % (db_user, db_pass, db_host, db_name), echo=False)
		
		# Grab our task
		sleep(0)
		
		task_query = sub_engine.execute(select([tasks], task_runs.c.task_id==tasks.c.id).where(task_runs.c.id==task_run))
		if not task_query.rowcount:
			log("Unable to find the task for task run %s!" % task_run)
			result = sub_engine.execute(task_runs.update().where(task_runs.c.id==task_run).values(failed_at=func.now(),started_at=func.now(),status="failed"))
			return False
		else:
			result = sub_engine.execute(task_runs.update().where(task_runs.c.id==task_run).values(started_at=func.now(),status="starting"))
		
		task = task_query.fetchone()

		sleep(0)
		
		decrypted = decrypt_dict(task['tenant_id'],{"config": task.config, "datastore": task.datastore})
		config_json = json.loads(decrypted['config'])
		datastore = decrypted.get('datastore')
		try:
			"something"
		except:
			log("Couldn't decode JSON for task run "+str(task_run))
			result = sub_engine.execute(task_runs.update().where(task_runs.c.id==task_run).values(failed_at=func.now(),started_at=func.now(),status="failed"))
			return False
		

		sleep(0)

		# Grab a accesskey
		
		accesskey_query = sub_engine.execute(select([accesskeys], accesskeys.c.tenant_id==task.tenant_id))
		if not accesskey_query.rowcount:
			log("Unable to find a accesskey for task run %s!" % task_run)
			result = sub_engine.execute(task_runs.update().where(task_runs.c.id==task_run).values(failed_at=func.now(),started_at=func.now(),status="failed"))
			return False
		else:
			result = sub_engine.execute(task_runs.update().where(task_runs.c.id==task_run).values(status="authenticating"))

		accesskey = accesskey_query.fetchone()


		sleep(0)

		# Grab a token
		decrypted = decrypt_dict(task['tenant_id'],{"accesskey": accesskey.accessKey, "secretkey": accesskey.secretKey})
		token = get_cs_token(accesskey=decrypted['accesskey'], secretkey=decrypted['secretkey'],
			identity_url=identity_url,tenant_id=task.tenant_id)
		
		if not token:
			log("Unable to get a token for task run %r with accesskey %r!" % (task_run, accesskey.id))
			result = sub_engine.execute(task_runs.update().where(task_runs.c.id==task_run).values(failed_at=func.now(),started_at=func.now(),status="failed"))
			return False
		else:
			result = sub_engine.execute(task_runs.update().where(task_runs.c.id==task_run).values(status="running"))
		
		# Make a post
		
		post_dict = {
			"credentials": {
				"tenantId": task.tenant_id,
				"identity_url": identity_url,
				"token": token
				},
			"agent_url": task.agent_url,
			"action": "execute",
			"config": config_json,
			"datastore": datastore,
			"service": {
				"api_url": api_url,
				"task_id": task.id,
				"task_run_id": task_run
				}
			}
		
		post_dict_json = json.dumps(post_dict)
		
		sleep(0)
		status = "succeeded"
		identity_req = urllib2.Request(runner_url, post_dict_json, {'Content-type':'application/json'})
		response = ""
		datastore = None
		try:
		
			# This really needs to be cleaned up to allow for
			# ignoring non-json encapsulated data in the stream.
			resp_obj = urllib2.urlopen(identity_req)
			resp_obj.fp._sock.recv(0)
			for response_line in iter(resp_obj.readline, ''):
				response_json = {}
				try:
					response_json = json.loads(response_line)
				except ValueError, e:
					pass
				if response_json:
					if response_json.get('type') == 'datastore':
						# We're keeping this for later.
						datastore = response_json.get('message')
					else:
						result = sub_engine.execute(task_run_messages.insert(),
							task_run_id=task_run,
							title=response_json.get("title"),
							message=response_json.get("message"),
							percent=response_json.get("percent"),
							type=response_json.get("type"))
						if response_json.get('type') == 'mail':
							# We need to send an email.

							log("Sending email to "+str(task.email)+" for "+str(response_json.get("title")))
							try:
								send_email(task,response_json,task_run)
							except Exception, e:
								log("Email error: "+str(e))
								pass
							
						if response_json.get('type') == 'fail':
							status = "failed"
						
				sleep(0)
			
			
		except urllib2.HTTPError, e:
			log("HTTP error posting to agent runner: "+str(e))
			result = sub_engine.execute(task_runs.update().where(task_runs.c.id==task_run).values(failed_at=func.now(),started_at=func.now(),status="failed"))
			return False
		except urllib2.URLError, e:
			log("HTTP error posting to agent runner: "+str(e))
			result = sub_engine.execute(task_runs.update().where(task_runs.c.id==task_run).values(failed_at=func.now(),started_at=func.now(),status="failed"))
			return False
		
		if datastore:
			log("Updating datastore for task "+str(task.id))
			encrypted = encrypt_dict(task['tenant_id'],{"datastore": datastore})
			result = sub_engine.execute(tasks.update().where(tasks.c.id==task.id).values(datastore=encrypted['datastore']))
			
		
		result = sub_engine.execute(task_runs.update().where(task_runs.c.id==task_run).values(status=status))
		log("Worker finished for task_run "+str(task_run))
		
		# This is a one-off, set it to complete.
		if task.interval == 0:
			result = sub_engine.execute(tasks.update().where(tasks.c.id==task.id).values(status="complete"))
		
	except Empty:
		pass

def send_email(task,message,task_run):
	"""
Send an email to the user.
	"""
	outer = MIMEMultipart()
	outer['Subject'] = 'CA Alert: '+message.get('title')
	outer['To'] = task.email
	outer['From'] = "email@address.com"

	files = message.get("attachments")

	text_contents = message.get('message')
	html_contents = message.get('html')
	if not html_contents:
		html_contents = "<pre>\n"+text_contents+"</pre>"

	text_template = open("ca-alert-email.txt").read()
	html_template = open("ca-alert-email.html").read()

	text_body = Template(text_template).substitute(TASK_ID=task.id,TASK_RUN_ID=task_run,
							CA_URL=api_url,
							EMAIL_ADDRESS=task.email,
							TASK_NAME=task.name,
							BODY=text_contents)

	html_body = Template(text_template).substitute(TASK_ID=task.id,TASK_RUN_ID=task_run,
							CA_URL=api_url,
							EMAIL_ADDRESS=task.email,
							TASK_NAME=task.name,
							BODY=html_contents)

	outer.preamble = text_body

	message_body = MIMEText(html_body, 'html')
	outer.attach(message_body)

	for file_entry in files:
		filename = file_entry.get("file-name")
		contents = base64.b64decode(file_entry.get("contents"))

		# Guess the content type based on the file's extension.  Encoding
		# will be ignored, although we should check for simple things like
		# gzip'd or compressed files.
		ctype, encoding = mimetypes.guess_type(filename)
		if ctype is None or encoding is not None:
			ctype = 'application/octet-stream'
		maintype, subtype = ctype.split('/', 1)
		if maintype == 'text':
			msg = MIMEText(contents, _subtype=subtype)
		elif maintype == 'image':
			msg = MIMEImage(contents, _subtype=subtype)
		elif maintype == 'audio':
			msg = MIMEAudio(contents, _subtype=subtype)
		else:
			msg = MIMEBase(maintype, subtype)
			msg.set_payload(contents)
			# Encode the payload using Base64
			encoders.encode_base64(msg)
		# Set the filename parameter
		msg.add_header('Content-Disposition', 'attachment', filename=filename)
		msg.add_header('Content-Id', "<"+filename+">")
		outer.attach(msg)
	# Now send or store the message
	composed = outer.as_string()
	log("Sending email to "+task.email)
	s = smtplib.SMTP('smtp.sendgrid.net', 587)
	s.login(sendgrid_user, sendgrid_pass)
	s.sendmail("email@address.com", task.email, composed)
	s.quit()


def configer(n):
	try:
		priority,config_request_id = config_tasks.get(timeout=1) # decrements queue size by 1
		log('Configer %s got config request %s at priority %s' % (n, config_request_id, priority))

		sub_engine = create_engine('mysql://%s:%s@%s/%s?charset=utf8' % (db_user, db_pass, db_host, db_name), echo=False)
		
		# Grab our task
		sleep(0)
		
		config_query = sub_engine.execute(select([config_requests], config_requests.c.id==config_request_id))
		if not config_query.rowcount:
			log("Unable to find config request %s!" % config_request_id)
			return False
		
		config_request = config_query.fetchone()

		sleep(0)
		
		# Grab a accesskey
		
		accesskey_query = sub_engine.execute(select([accesskeys], accesskeys.c.tenant_id==config_request.tenant_id))
		if not accesskey_query.rowcount:
			log("Unable to find a accesskey for config request %s!" % config_request_id)
			result = sub_engine.execute(config_requests.update().where(config_requests_id.c.id==config_request_id).values(status="failed"))
			return False

		accesskey = accesskey_query.fetchone()

		sleep(0)

		# Grab a token

		decrypted = decrypt_dict(config_request['tenant_id'],{"accesskey": accesskey.accessKey, "secretkey": accesskey.secretKey})
		token = get_cs_token(accesskey=decrypted['accesskey'], secretkey=decrypted['secretkey'],
			identity_url=identity_url,tenant_id=config_request.tenant_id)
				
		if not token:
			log("Unable to get a token for config request %r with accesskey %r!" % (config_request_id, accesskey.id))
			result = sub_engine.execute(config_requests.update().where(config_requests.c.id==config_request_id).values(status="failed"))
			return False
		
		# Make a post
		
		post_dict = {
			"credentials": {
				"tenantId": config_request.tenant_id,
				"identity_url": identity_url,
				"token": token
				},
			"agent_url": config_request.agent_url,
			"action": "config",
			"config": {},
			"service": {
				"api_url": api_url
				}
			}
		
		post_dict_json = json.dumps(post_dict)
		
		sleep(0)
		config = None
		identity_req = urllib2.Request(runner_url, post_dict_json, {'Content-type':'application/json'})
		try:
			
			for response in urllib2.urlopen(identity_req).readlines():

				try:
					response_json = json.loads(response)
				except ValueError, e:
					pass
					
				if response_json.get('config') != None:
					result = sub_engine.execute(config_requests.update().where(config_requests.c.id==config_request_id).values(config=response,status='success'))
					log("Config found for config request",config_request_id)
					return True
				sleep(0)
				
			if not config:
		
				log("Configuration unparseable for config request %r:" % (config_request_id))
				result = sub_engine.execute(config_requests.update().where(config_requests.c.id==config_request_id).values(status="failed"))
				return False

		except urllib2.HTTPError, e:
			log("HTTP error posting to agent runner.")
			result = sub_engine.execute(config_requests.update().where(config_requests.c.id==config_request_id).values(status="failed"))
			return False

		log("Configer finished for config_request "+str(config_request_id))
				
	except Empty:
		pass

def boss():
	#select id,url,post_value from jobs where unix_timestamp(last_scheduled_at) <= unix_timestamp()-interval_in_seconds or last_scheduled_at is null and is_active=1 limit 1;

	main_engine = create_engine('mysql://%s:%s@%s/%s?charset=utf8' % (db_user, db_pass, db_host, db_name))


	while not trigger_shutdown:


		select_query = text("""
			select id from config_requests where config is null and status = 'queued';
		""")
		
		results = main_engine.execute(select_query)
		if results.rowcount:
			for result in results.fetchall():
				update_query = text("UPDATE config_requests SET status='running' WHERE id = :config_request_id")
				sub_results = main_engine.execute(update_query, config_request_id=result.id)
				config_tasks.put((0,result.id))
				worker_thread = gevent.spawn(configer,str(result.id))


		# Loop till we die.
		if gevent_tasks.qsize() >= max_workers:
			# Wait till the pool isn't full.
			sleep(0)
		else:

			# One time tasks.

			sleep_time = 1
			select_query = text("""
				select id from tasks where (unix_timestamp(last_scheduled_at) <= unix_timestamp()-tasks.interval or last_scheduled_at is null) and unix_timestamp(tasks.start_at) <= unix_timestamp() and status="active" and tasks.interval = 0 limit 1;
			""")
			results = main_engine.execute(select_query)
			if results.rowcount:
			
				sleep_time = 0
				for result in results.fetchall():
					# Update our last_scheduled_at time, pushing us into the future.
					update_query = text("UPDATE tasks SET last_scheduled_at=now(),status='running' WHERE id = :task_id")
					sub_results = main_engine.execute(update_query,task_id=result.id)
					# See if we already have a queue task waiting for us.
					existing_task_run = main_engine.execute(select([task_runs], task_runs.c.task_id==result.id).where(task_runs.c.status=="queued"))
					if existing_task_run.rowcount:
						row = existing_task_run.fetchone()
						log("Adding task "+str(row.id))
						gevent_tasks.put((2,row.id))
						worker_thread = gevent.spawn(worker,str(row.id))
					else:
						task_run_insert = main_engine.execute(task_runs.insert(), task_id=result.id, status="queued")
						log("Adding task "+str(task_run_insert.lastrowid))
						gevent_tasks.put((2,task_run_insert.lastrowid))
						worker_thread = gevent.spawn(worker,str(task_run_insert.lastrowid))
			else:
			
				# Recurring tasks.
	
				select_query = text("""
					select id, unix_timestamp(last_scheduled_at) as last_scheduled_at, tasks.interval, unix_timestamp() as now from tasks where (unix_timestamp(last_scheduled_at) <= unix_timestamp()-tasks.interval or last_scheduled_at is null) and unix_timestamp(tasks.start_at) <= unix_timestamp() and status="active" and tasks.interval > 0 limit 1;
				""")
				results = main_engine.execute(select_query)
				
				if results.rowcount:
					sleep_time = 0
					for result in results.fetchall():
						# Update our last_scheduled_at time, pushning us into the future.
						#print result.last_scheduled_at," + (((",result.now," - ",result.last_scheduled_at,") / ",result.interval,") * ",result.interval,")"
						last_scheduled_at = result.last_scheduled_at + (((result.now - result.last_scheduled_at) / result.interval) * result.interval)
						#print "New Last Run At:",last_scheduled_at
						update_query = text("UPDATE tasks SET last_scheduled_at=from_unixtime(:last_scheduled_at) WHERE id = :task_id")
						sub_results = main_engine.execute(update_query,last_scheduled_at=last_scheduled_at,task_id=result.id)
						# See if we already have a queue task waiting for us.
						existing_task_run = main_engine.execute(select([task_runs], task_runs.c.task_id==result.id).where(task_runs.c.status=="queued"))
						if existing_task_run.rowcount:
							row = existing_task_run.fetchone()
							log("Adding task "+str(row.id))
							gevent_tasks.put((2,row.id))
							worker_thread = gevent.spawn(worker,str(row.id))
						else:
							task_run_insert = main_engine.execute(task_runs.insert(), task_id=result.id, status="queued")
							log("Adding task " +str(task_run_insert.lastrowid))
							gevent_tasks.put((2,task_run_insert.lastrowid))
							worker_thread = gevent.spawn(worker,str(task_run_insert.lastrowid))

			sleep(sleep_time)

	if gevent_tasks.qsize() > 0:
		# Wait till the pool is empty.
		sleep(0)


	
def get_cs_token(accesskey="",secretkey="",identity_url="",tenant_id=""):
	"""
	Pass our accesskey and secretkey to keystone for tokenization.
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
		log("HTTP Error: "+str(e))
		return False
	response_json = json.loads(response)
	if response_json['access']['token']['tenant']['id'] == tenant_id:
		return response_json['access']['token']['id']
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
		try:
			junk,crypt_type,junk = message.split("-",3)
			if crypt_type == 'base64':
				output[identifier] = b64decode(message)
			else:
				values[identifier] = message
		except:
			# Our value isn't valid, ignore it.
			pass
	
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

def shutdown(*args):
	global trigger_shutdown
	log("Triggering Shutdown.")
	trigger_shutdown = True

def log(message):
	print strftime("[%Y-%m-%d %H:%M:%S] ")+str(message)

if __name__ == "__main__":



	config = ConfigParser.RawConfigParser()
	config.read('ca.cfg')

	identity_url = config.get('Dispatch','identity_url')
	max_workers = int(config.get('Dispatch','max_workers'))
	db_host = config.get('Dispatch','db_host')
	db_user = config.get('Dispatch','db_user')
	db_pass = config.get('Dispatch','db_pass')
	db_name = config.get('Dispatch','db_name')
	runner_url = config.get('Dispatch','runner_url')
	api_url = config.get('Dispatch','api_url')
	crypt_url = config.get('Dispatch','crypt_url')
	crypt_method = config.get('Dispatch','crypt_method')
	sendgrid_user = config.get('Dispatch','sendgrid_user')
	sendgrid_pass = config.get('Dispatch','sendgrid_pass')

	socket._fileobject.default_bufsize = 0

	# Same as agents_api
	
	metadata = MetaData()
	accesskeys = Table('accesskeys', metadata,
		Column('id', Integer, primary_key=True),
		Column('accessKey', String(200)),
		Column('secretKey', String(200)),
		Column('tenant_id', String(100), index=True),
		UniqueConstraint('accessKey', 'tenant_id', name="tenantkeys"),
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

	signal.signal(signal.SIGTERM, shutdown)
	trigger_shutdown = False
	
	gevent_tasks = PriorityQueue()
	config_tasks = PriorityQueue()
	sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

	log("Starting up.")
	gevent.joinall([gevent.spawn(boss)])
	

