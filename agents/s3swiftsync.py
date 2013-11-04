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

ca = CloudAgent()

ca.required_config = {
	"name": "S3 to Swift Sync",
	"version": "0.2.0",
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This script copies files from S3 to Swift which don't exist in Swift.""",
	"config":
		[{
			"name": "s3bucket",
			"regexp": "^.{1,100}$",
			"title": "S3 Bucket",
			"description": "Bucket in s3 to copy from.",
			"type": "string",
			"required": True
		},{
			"name": "s3accesskey",
			"regexp": "^.{1,100}$",
			"title": "S3 Access Key",
			"description": "Access Key for S3 Service.",
			"type": "string",
			"required": True
		},{
			"name": "s3secretkey",
			"regexp": "^.{1,100}$",
			"title": "S3 Secret Key",
			"description": "Secret Key for S3 Service.",
			"type": "string",
			"required": True
		},{
			"name": "region",
			"regexp": "^.{1,100}$",
			"title": "Swift Region",
			"description": "Region location for swift target container.",
			"type": "string",
			"required": True,
			"resource": "openstack.object-store.endpoints.region"
		},{
			"name": "container",
			"regexp": "^.{1,100}$",
			"title": "Swift Container",
			"description": "Name of swift target container.",
			"type": "string",
			"required": True,
			"resource": "openstack.object-store.[region].containers"
		},{
			"name": "emailreport",
			"title": "Email Report",
			"description": "Send an email report if files were synced.",
			"type": "boolean",
			"default": False,
			"required": False
		}
		]
	}

def agent():

	from gevent import monkey, sleep; monkey.patch_all()
	from gevent.pool import Pool
	import gevent
	from time import sleep
	from boto.s3.connection import S3Connection
	global S3Connection
	from boto.s3.key import Key
	global Key
	from boto.s3.bucket import Bucket
	global Bucket
	from keystoneclient.v2_0 import client
	global client
	import swiftclient
	global swiftclient
	import urllib2
	global urllib2

	ca.log("Starting.",'',5)

	# Connect to swift and find our endpoint

	keystone = client.Client(token=ca.creds['token'], tenant_id=ca.creds['tenantId'],
							auth_url=ca.creds['identity_url'])
	
	object_store_catalog = keystone.service_catalog.get_endpoints()['object-store']
	
	global region_endpoints
	
	for endpoints in object_store_catalog:
		if endpoints['region'] == ca.conf['region']:
			region_endpoints = endpoints
	
	if not region_endpoints:
		ca.log_fail("Failing, region not found in endpoint list.")
		exit()

	# Get our container listing, if the container exists.
	
	try:
		files = get_swift_container(region_endpoints['publicURL']+"/"+ca.conf['container'],ca.creds['token'])

	except StandardError,e:
		print "Got error!",e
		files = []


	s3 = S3Connection(ca.conf['s3accesskey'].encode('ascii'), ca.conf['s3secretkey'].encode('ascii'))

	bucket = s3.get_bucket(ca.conf['s3bucket'])
		
	swiftclient.put_container(region_endpoints['publicURL'],ca.creds['token'],ca.conf['container'])

	max_workers = 5
	pool = Pool(max_workers)

	global copied_files
	copied_files = []
	for key in bucket:
		#ca.log("Found "+key.name)
# 		if key.name[-1] == "/":
# 			if not key.name[0:-1] in files:
# 				pool.apply_async(worker, args=(region_endpoints['publicURL'],
# 									ca.conf['swiftcontainer'],
# 									ca.creds['token'],
# 									key.name,
# 									ca.conf['s3bucket'],
# 									ca.conf['s3accesskey'].encode('ascii'),
# 									ca.conf['s3secretkey'].encode('ascii')))
		if not key.name in files:
				pool.apply_async(worker, args=(region_endpoints['publicURL'],
												ca.conf['container'],
												ca.creds['token'],
												key.name,
												ca.conf['s3bucket'],
												ca.conf['s3accesskey'].encode('ascii'),
												ca.conf['s3secretkey'].encode('ascii')))

	pool.join()
	
	if ca.conf.get('emailreport') and copied_files:
		ca.log("Sending email.")
		ca.email("Copied "+str(len(copied_files))+" files to "+ca.conf['container'],'''
	Copied the follow files from S3 bucket %s to Swift container %s:
	
%s
	''' % (ca.conf['s3bucket'],ca.conf['container'],"\n".join(copied_files)))

	ca.log("Done.",'',100)

		
		


def worker(endpoint,container,token,key_name,bucket,accesskey,secretkey):


	#ca.log("Starting "+str(key_name))
	my_s3 = S3Connection(accesskey,secretkey)
	my_bucket = Bucket(connection=my_s3, name=bucket)
	key = Key(my_bucket)
	key.key = key_name
	if key.name[-1] == "/" and key.size == 0:
		swiftclient.put_object(endpoint,container=container,
					token=token,name=key.name,contents=key,
					content_type="application/directory")
	else:
		swiftclient.put_object(endpoint,container=container, token=token,name=key.name,
								contents=key)
	copied_files.append(key.name)
	ca.log("Uploaded "+key.name)

def get_swift_container(url,token,max=100000):
	"""
	Returns a list of files in a specific container.
	Pass in max if you want to return an error if there
	are more than a set number of files in the container.
	A 100,000 item list will likely take 20-30 meg of ram.
	"""
	
	files = []

	while True:
		if len(files):
			request = urllib2.Request(url+"?marker="+urllib2.quote(files[-1]),None, {'X-Auth-Token':token})
			try:
				response = urllib2.urlopen(request)
			except urllib2.HTTPError, e:
				return files

			file_list = response.read().splitlines()
			
		else:
			request = urllib2.Request(url,None, {'X-Auth-Token':token})
			try:
				response = urllib2.urlopen(request)
			except urllib2.HTTPError, e:
				return []

			file_list = response.read().splitlines()
		
		
		files += file_list
		if len(files) >= max:
			raise StandardError

		if len(file_list) < 10000:
			file_list = None
			break
		

	return files	
	

ca.run(agent)
