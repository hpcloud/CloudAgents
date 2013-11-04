#!/usr/bin/env python

# Copyright 2013 Hewlett-Packard Development Company, L.P.
# All Rights Reserved.

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#      http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.


import json
import argparse
import os
from sys import stdin, stderr, exit
import re
import urllib2
import base64

class CloudAgent:
	
	required_config = {}
	
	def __init__(self):
	
		parser = argparse.ArgumentParser(
			formatter_class=argparse.RawDescriptionHelpFormatter,
			description='''Run a Cloud Agent.''',epilog=''''''	)
		parser.add_argument('-c',dest='config', action='store_true',
			help='output configuration')
		parser.add_argument('-v',dest='validate', action='store_true',
			help='validate configuration, but do not execute agent')
		parser.add_argument('-j',dest='json', action='store_true',
			help='output log in json')
		parser.add_argument('-t',dest='pretty', action='store_true',
			help='output log in text, titles to STDOUT, messages to STDERR (Default)', default=True)
		parser.add_argument('-f',dest='json_file', type=str,
			help='read config json from named file')
		parser.add_argument('-i',dest='stdin', action='store_true',
			help='read config json from STDIN')
		parser.add_argument('-I',dest='interactive', action='store_true',
			help='read configuration interactively')
		parser.add_argument('-a', dest="args", type=str,
			help="additional agent script arguments")
		parser.add_argument('-e',dest='environment', action='store_true',
			help='read credentials from environment variables')
		parser.add_argument('-E',dest='keystoneenv', action='store_true',
			help='read access credentials from environment variables and request token')
		parser.add_argument('-d',dest='datastore_file', type=str,
			help='read/write datastore from file')
		args = parser.parse_args()
	
		if args.config:
			self.action = "config"
		elif args.validate:
			self.action = "validate"
		else:
			self.action = "execute"	
		
		if args.json:
			self.print_style = 'json'
		else:
			self.print_style = 'text'
		
		data = "{}"
	
		if (args.json_file):
			data = open(args.json_file).read()
		elif (args.stdin):
			data = stdin.read()
			
		try:
			json_data = json.loads(data)
		except ValueError, e:
			self.log("Error parsing JSON!",e)
			raise ValueError
		
		if json_data.get('credentials'):
			self.creds = json_data['credentials']
		else:
			self.creds = {}
			
		if args.environment:
			if os.getenv('CA_TOKEN'):
				self.creds['token'] = os.getenv('CA_TOKEN')
			if os.getenv('CA_TENANT_ID'):
				self.creds['tenantId'] = os.getenv('CA_TENANT_ID')
			if os.getenv('CA_IDENTITY_URL'):
				self.creds['identity_url'] = os.getenv('CA_IDENTITY_URL')		

		if args.keystoneenv:
			if os.getenv('OS_TENANT_ID'):
				self.creds['tenantId'] = os.getenv('OS_TENANT_ID')
			else:
				raise StandardError("Missing OS_TENANT_ID env variable.")
				
			if os.getenv('OS_IDENTITY_URL'):
				self.creds['identity_url'] = os.getenv('OS_IDENTITY_URL')
			else:
				raise StandardError("Missing OS_IDENTITY_URL env variable.")
				
			if os.getenv('OS_USERNAME') and os.getenv('OS_PASSWORD'):
				self.creds['token'] = self.get_keystone_token(username=os.getenv('OS_USERNAME'),
													password=os.getenv('OS_PASSWORD'),
													tenant_id=os.getenv('OS_TENANT_ID'),
													identity_url=os.getenv('OS_IDENTITY_URL'))
			elif os.getenv('OS_SECRETKEY') and os.getenv('OS_ACCESSKEY'):
				self.creds['token'] = self.get_keystone_token(accesskey=os.getenv('OS_ACCESSKEY'),
													secretkey=os.getenv('OS_SECRETKEY'),
													tenant_id=os.getenv('OS_TENANT_ID'),
													identity_url=os.getenv('OS_IDENTITY_URL'))
			else:
				raise StandardError("Missing OS_USERNAME and OS_PASSWORD or OS_ACCESSKEY and OS_SECRETKEY env variables.")

		if json_data.get('config'):
			self.conf = json_data['config']
		else:
			self.conf = {}

		if json_data.get('service'):
			self.service = json_data['service']
		else:
			self.service = {}

		if json_data.get('datastore'):
			self.datastore = json_data['datastore']
		else:
			self.datastore = None
			
		self.datastore_file = None
		if args.datastore_file:
			try:
				self.datastore = open(args.datastore_file).read()
			except IOError, e:
				pass
				
			self.datastore_file = args.datastore_file

		if args.interactive:
			self.interactive = True
		else:
			self.interactive = False
		

	def log_fail(self,title,message="",percent=None):
		self.log(title,message,percent,type="fail")

	def log_warn(self,title,message="",percent=None):
		self.log(title,message,percent,type="warn")

	def log_note(self,title,message="",percent=None):
		self.log(title,message,percent,type="note")

	def log(self,title,message="",percent=None,type="note"):
		"""
		Log message types:
		
		note  - general output
		sys   - system data
		fail - agent did not run as requested
		warn - agent running potentially harmfully
		"""
	
		if self.print_style == 'json':
			if percent:
				print json.dumps({"title":title,"message":message,"percent":percent,"type":type})
			else:
				print json.dumps({"title":title,"message":message,"type":type})
		elif self.print_style == "text":
			if percent:
				print "#", title, "(%" + str(percent) + ")"
			else:
				print "#", title
			if message:
				print >> stderr, message

	def store(self,message):
		"""
		Make a request to store data.
		"""
		if self.datastore_file:
			storefile = open(self.datastore_file, 'w')
			storefile.write(message)
			storefile.close()
		else:
			if self.print_style == 'json':
				print json.dumps({"message":message,"type":"datastore"})
			elif self.print_style == "text":
					print >> stderr, str("Trying to store:\n",message)

		

	def email(self,title,message, html="",attachments=[]):
		"""
title: Email title
message: Text Message Body
html: HTML Message Body (optional)
attachments: (optional list)
	file-name: Name of Attachment file
	contents: Attachment File contents
	content-type: Attachment Content-Type (optional)
		"""
		if self.print_style == 'json':
			attachments64 = []
			for attachment in attachments:
				attachments64.append({"file-name":attachment['file-name'],
										"contents":base64.b64encode(attachment['contents']),
										"content-type":attachment.get('content-type')})
			print json.dumps({"title":title,"message":message,"html":html,"attachments":attachments64,"type":"mail"})
		elif self.print_style == "text":
			print "# Email Requested."
			print "# Subject: ", title
			print "# Message:"
			print message
			for attachment in attachments:
				print "# Attaching: "+attachment['file-name']
			
	def print_required_config(self):
		if self.print_style == 'text':
			print json.dumps(self.required_config, sort_keys=True, indent=4)
		else:
			print json.dumps(self.required_config)
	
	def validate_config(self):
		for var in self.required_config['config']:
			if (self.conf.get(var['name']) == '') and var.get('required') == False:
				continue
			if (self.conf.get(var['name']) == None) and var.get('required') == False:
				continue			
			if (self.conf.get(var['name']) == None) and var.get('required'):
				self.log_fail("Error!  Config not found: "+var['name'])
				exit()
			if var.get('regexp'):
				if not re.match(var['regexp'],self.conf.get(var['name'])):
					self.log_fail("Error!  "+var['title']+" value doesn't match: "+self.conf.get(var['name'])+" vs /"+var['regexp']+"/")
					exit()
		return True

	def get_keystone_token(self,**args):
		'''
		Gets a keystone token from a keystone identity service.
		'''
		if 'accesskey' in args:
			identity_request = {
				'auth' : {
					'apiAccessKeyCredentials' : {
						'accessKey' : args['accesskey'],
						'secretKey' : args['secretkey']
					},
					"tenantId": args['tenant_id']
				}
			}
		elif 'username' in args:
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
	
	def run(self,agent=None):
		if self.action == "config":
			self.print_required_config()
		elif self.action == "validate":
			if self.validate_config():
				self.log("Config passes validation.")
		elif self.action == "execute":
			if self.interactive:
				for option in self.required_config.get('config'):
					print option.get('description')
					if option['type'] == 'string':
						self.conf[option['name']] = raw_input(self.bold(option['title']+": "))
					elif option['type'] == 'select':
						print self.bold("Options: "),
						for suboption in option['options']:
							print suboption['name']+" ("+suboption['value']+")"
						self.conf[option['name']] = raw_input(option['title']+": ")
					elif option['type'] == 'boolean':
						response = raw_input(self.bold(option['title']+" (y/n): "))
						if response == 'y':
							self.conf[option['name']] = True
						elif response == 'n':
							self.conf[option['name']] = False
						else:
							print "Didn't understand, exiting."
							sys.exit()
						
			if self.validate_config():
				agent()

	def bold(self,msg):
		return u'\033[1m%s\033[0m' % msg