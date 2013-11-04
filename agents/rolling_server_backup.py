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
import keystoneclient.v2_0
import novaclient.v1_1
import time

ca = CloudAgent()

ca.required_config = {
	"name": "Rolling Server Backup",
	"version": "0.1.0",
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This script cycles backups for a selected server.""",
	"config":
		[{
			"name": "name",
			"regexp": "^.{1,50}$",
			"title": "Server Name",
			"description": "Name of the server to backup.",
			"type": "string",
			"required": True,
			"resource": "openstack.compute.[region].servers"
		},{
			"name": "region",
			"regexp": "^.{1,50}$",
			"title": "Zone",
			"description": "Compute zone to create the server in (ie: az-2.region-a.geo-1).",
			"type": "string",
			"required": True,
			"resource": "openstack.compute.endpoints.region"
		},{
			"name": "daily",
			"title": "Daily Backups",
			"description": "Number of daily backups to keep.",
			"type": "select",
			"required": True,
			"options": [
				{"name": "0", "value": "0"},
				{"name": "1", "value": "1"},
				{"name": "2", "value": "2"},
				{"name": "3", "value": "3"},
				{"name": "4", "value": "4"},
				{"name": "5", "value": "5"},
				{"name": "6", "value": "6"},
				{"name": "7", "value": "7"},
				]
		},{
			"name": "weekly",
			"title": "Weekly Backups",
			"description": "Number of weekly backups to keep.",
			"type": "select",
			"required": True,
			"options": [
				{"name": "0", "value": "0"},
				{"name": "1", "value": "1"},
				{"name": "2", "value": "2"},
				{"name": "3", "value": "3"},
				{"name": "4", "value": "4"},
				{"name": "5", "value": "5"},
				{"name": "6", "value": "6"},
				{"name": "7", "value": "7"},
				]
		},{
			"name": "weeklyday",
			"title": "Weekly Day",
			"description": "Day of the week to run weekly backup.",
			"type": "select",
			"required": True,
			"options": [
				{"name": "Sunday", "value": "0"},
				{"name": "Monday", "value": "1"},
				{"name": "Tuesday", "value": "2"},
				{"name": "Wednesday", "value": "3"},
				{"name": "Thursday", "value": "4"},
				{"name": "Friday", "value": "5"},
				{"name": "Saturday", "value": "6"}
				]
		}
		]
	}

def agent():
	
	ca.log("Starting!",'',1)
	
	keystone = keystoneclient.v2_0.client.Client(token=ca.creds['token'], tenant_id=ca.creds['tenantId'],
							auth_url=ca.creds['identity_url'])
	
	compute_catalog = keystone.service_catalog.get_endpoints()['compute']
	
	cluster_endpoint = None
	
	for endpoint in compute_catalog:
		if endpoint['region'] == ca.conf['region']:
			cluster_endpoint = endpoint
	
	if not cluster_endpoint:
		ca.log_fail("Failing, region not found in endpoint list.")
		exit()
	
	nova = novaclient.v1_1.client.Client(None,None,None,auth_url="")
	nova.set_management_url(cluster_endpoint['publicURL'])
	nova.client.auth_token = ca.creds['token']
	
	# Get the image we're supposed to use.
	
	target_server = None

	for server in nova.servers.list():
		if server.name == ca.conf['name']:
			target_server = server
	
	if not target_server:
		ca.log_fail("Failing, server "+ca.conf['name']+" not found in "+ca.conf['region']+".")
		exit()
	
	ca.log("Found server: "+target_server.name+" ("+str(target_server.id)+")",'',4)


	# First, we run our backups.
	
	if ca.conf['daily'] > 0:
		backup_server(target_server,target_server.name+" Daily Backup "+time.strftime("%Y-%m-%d"),nova)
	if ca.conf['weekly'] > 0 and time.strftime("%w") == ca.conf['weeklyday']:
		backup_server(target_server,target_server.name+" Weekly Backup "+time.strftime("%Y-%m-%d"),nova)


	ca.log("Looking for backup images to trim.","")
	
	daily_images = {}
	weekly_images = {}
	for image in nova.images.list():
		if image.name.startswith(target_server.name+" Daily Backup "):
			daily_images[image.name] = image.id
		if image.name.startswith(target_server.name+" Weekly Backup "):
			weekly_images[image.name] = image.id

	# Then we trim the old ones.  If we got this far, the backups succeeded.
	
	for c,image in enumerate(sorted(daily_images.keys(),reverse=True)):
		if c+1 > int(ca.conf['daily']):
			ca.log("Deleting daily backup "+str(c+1)+": "+image+" ("+daily_images[image]+")","")
			nova.images.delete(daily_images[image])
			time.sleep(1)

	for c,image in enumerate(sorted(weekly_images.keys(),reverse=True)):
		if c+1 > int(ca.conf['weekly']):
			ca.log("Deleting weekly backup "+str(c+1)+": "+image+" ("+weekly_images[image]+")","")
			nova.images.delete(weekly_images[image])
			time.sleep(1)		

	ca.log("Backup complete.","")

def backup_server(server,backup_name,nova):
	# Run backup
	ca.log("Starting backup: "+backup_name,"")

	for image in nova.images.list():
		if image.name == backup_name:
			ca.log("Deleting pre-existing backup with the same name.","")
			nova.images.delete(image.id)
			time.sleep(1)
	
	server.create_image(backup_name)
	
	time.sleep(5)
	
	while True:
		my_image = None
		for image in nova.images.list():
			if image.name == backup_name:
				my_image = image
		if not my_image:
			ca.log_fail("Backup not found, image service may be down.","")
			exit()
		if my_image.status != 'SAVING':
			if my_image.status == "ACTIVE":
				ca.log("Backup succeeded.","")
				break
			else:
				ca.log_fail("Backup entered unexpected status: "+my_image.status+", failing.","")
				exit()
		time.sleep(5)

ca.run(agent)
