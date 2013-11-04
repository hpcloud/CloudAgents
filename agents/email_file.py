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
from keystoneclient.v2_0 import client
import swiftclient
from time import mktime
import datetime
import parsedatetime.parsedatetime as pdt

ca = CloudAgent()

ca.required_config = {
	"name": "Email File",
	"version": "0.1.0",
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This script sends an alert to a user including a file from a swift container.""",
	"config":
		[{
			"name": "region",
			"regexp": "^.{1,50}$",
			"title": "Region",
			"description": "Short name for the object storage endpoint region to search.  IE: region-a.geo-1",
			"type": "string",
			"required": True,
			"resource": "openstack.object-store.endpoints.region"
		},{
			"name": "container",
			"regexp": "^.{1,50}$",
			"title": "Container",
			"description": "Name of the container to search for the file.",
			"type": "string",
			"required": True,
			"resource": "openstack.object-store.[region].containers"
		},{
			"name": "date",
			"regexp": "^.{1,250}$",
			"title": "Date Adjustment",
			"description": "Date adjustment.  Enables time substitution in object name.  IE: 'yesterday'.  Dates are compared in UTC.",
			"type": "string",
			"required": False,
		},{
			"name": "name",
			"regexp": "^.{1,250}$",
			"title": "Name",
			"description": "Object name to email from the container.  If a date adjustment is set, python datetime time substution is enabled.  IE: 'reports/%Y-%m-%d.txt'",
			"type": "string",
			"required": True
		},
		]
	}

def agent():
	
	ca.log("Starting!")
	
	keystone = client.Client(token=ca.creds['token'], tenant_id=ca.creds['tenantId'],
							auth_url=ca.creds['identity_url'])
	
	object_store_catalog = keystone.service_catalog.get_endpoints()['object-store']
	
	region_endpoints = None
	
	for endpoints in object_store_catalog:
		if endpoints['region'] == ca.conf['region']:
			region_endpoints = endpoints
	
	if not region_endpoints:
		ca.log_fail("Failing, region not found in endpoint list.")
		exit()
	
	if ca.conf.get('date'):
		p = pdt.Calendar()
		result = p.parse(ca.conf['date'])
		dt = datetime.datetime.fromtimestamp(mktime(result[0]))
		path = dt.strftime(ca.conf['name'])
	else:
		path = ca.conf['name']
	
	try:
		headers, contents = swiftclient.get_object(region_endpoints['publicURL'],ca.creds['token'],
												ca.conf['container'],path)
		if headers['content-length'] >= 0:
			ca.log("Emailing file!")
			file_name = path.split("/")[-1]
			ca.email(path,'''
	Here is the file '%s' from the container '%s'.
	''' % (ca.conf['container'], path), None, [{"file-name":file_name,"contents":contents}])
			
	except swiftclient.client.ClientException, e:
		ca.log("File doesn't exist!")
		ca.email("File missing: "+ca.conf['container']+"/"+path,'''
	The container '%s' appears to be missing the file '%s'.
	''' % (ca.conf['container'], path))
		

ca.run(agent)
