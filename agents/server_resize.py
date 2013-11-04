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
	"name": "Server Resize",
	"version": "0.1.0",
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This script resizes a server by snapshotting it, creating a new larger server with the snapshot, and moving the floating IP.""",
	"config":
		[{
			"name": "name",
			"regexp": "^.{1,50}$",
			"title": "Server Name",
			"description": "Name of the server to resize.",
			"type": "string",
			"required": True,
			"resource": "openstack.compute.[region].servers"
		},{
			"name": "newname",
			"regexp": "^.{1,50}$",
			"title": "New Server Name",
			"description": "Name for the resized server (must be different than the existing server name).",
			"type": "string",
			"required": True
		},{
			"name": "region",
			"regexp": "^.{1,50}$",
			"title": "Zone",
			"description": "Compute zone to create the server in (ie: az-2.region-a.geo-1).",
			"type": "string",
			"required": True,
			"resource": "openstack.compute.endpoints.region"
		},{
			"name": "flavor",
			"regexp": "^.{1,20}$",
			"title": "Flavor",
			"description": "Flavor/size of the server to migrate to (ie: standard.xsmall).",
			"type": "string",
			"required": True,
			"resource": "openstack.compute.[region].flavors"
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

	# Get the flavor we're supposed to use.
	
	requested_flavor = None
	
	for flavor in nova.flavors.list():
		if flavor.name == ca.conf['flavor']:
			requested_flavor = flavor
	
	if not requested_flavor:
		ca.log_fail("Failing, flavor "+ca.conf['flavor']+" not found.")
		exit()
	
	ca.log("Found flavor.",'',3)

	# Get the floating ip we're migrating.
	
	floating_ip = None

	for ip in nova.floating_ips.list():
		if target_server.id == ip.instance_id:
			floating_ip = ip
	
	if not floating_ip:
		ca.log_fail("Failing, floating ip for server "+ca.conf['name']+" not found in "+ca.conf['region']+".  We can only resize servers with floating IPs.")
		exit()
	
	ca.log("Found floating ip: "+floating_ip.ip+" ("+str(floating_ip.id)+")",'',5)
	
	# First, we run our backups.
	
	backup_server(target_server,target_server.name+" Migration Snapshot",nova)

	
	snapshot_image = None
	
	for image in nova.images.list():
		if image.name == target_server.name+" Migration Snapshot":
			snapshot_image = image

	ca.log("OS snapshot complete.","",40)
	security_groups = []
	for group in target_server.security_groups:
		security_groups.append(group['name'])

	ca.log("Creating new server.","",41)
	
	new_server_id = nova.servers.create(ca.conf['newname'],
									snapshot_image,
									requested_flavor,
									security_groups=security_groups,
									key_name=target_server.key_name)

	time.sleep(5)
	new_server = nova.servers.get(new_server_id)
	c = 5
	while new_server.status != 'ACTIVE' or c > 120:
		new_server = nova.servers.get(new_server_id)
		time.sleep(5)
		c += 5
		
	if new_server.status != 'ACTIVE':
		ca.log_fail("New server didn't boot in 2 minutes, deleting new server and snapshot.")
		nova.servers.delete(new_server)
		nova.images.delete(snapshot_image.id)
		exit()

	ca.log("New server created.",'',85)
	
	target_server.remove_floating_ip(floating_ip.ip)
	time.sleep(1)
	new_server.add_floating_ip(floating_ip.ip)
	
	ca.log("IP migrated to new server.","",95)

	nova.images.delete(snapshot_image.id)
	
	ca.log("Removed migration snapshot, resize complete.","",100)

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
