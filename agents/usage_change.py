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
import novaclient.v1_1
import json
import urllib2
from collections import defaultdict
import StringIO
import csv

ca = CloudAgent()

ca.required_config = {
	"name": "Usage Change",
	"version": "0.1.0",
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This script audits what resources you're using across the cloud, and sends you a notification with details and changes.""",
	"config":
		[
		]
	}

def agent():
	
	ca.log("Starting!")
	
	keystone = client.Client(token=ca.creds['token'], tenant_id=ca.creds['tenantId'],
							auth_url=ca.creds['identity_url'])
	
	catalog = keystone.service_catalog.catalog
	text = ""
	if ca.datastore:
		old_usage = json.loads(ca.datastore)
	else:
		old_usage = AutoVivification()
	usage = AutoVivification()
	changes = AutoVivification()
	object_csv_data = []
	compute_csv_data = []
	files = []

	for entry in catalog['serviceCatalog']:
		if entry['type'] == 'object-store':
			text += "\nObject Storage\n--------------\n\n"
			text += "%-15s %-25s %10s %10s %10s\n" % ("Region", "Container", 
													"Objects", 
													"Size", 
													"$/month")
			for endpoint in entry['endpoints']:
				headers, containers = swiftclient.get_account(endpoint['publicURL'], 
										ca.creds['token'],full_listing=True)
				for container in containers:
					try: 
						old_container = old_usage['object-store'][endpoint['region']][container['name']]
					except ValueError:
						old_container = dict
					if old_container.get('count',0) != container['count'] or old_container.get('bytes',0) != container['bytes']:
						if old_container.get('bytes',0) < container['bytes'] or old_container.get('count',0) < container['count']:
							changes['object-store'][endpoint['region']][container['name']]['bytes'] = container['bytes'] - old_container.get('bytes',0)
							changes['object-store'][endpoint['region']][container['name']]['count'] = container['count'] - old_container.get('count',0)

					usage['object-store'][endpoint['region']][container['name']]['count'] = container['count']
					usage['object-store'][endpoint['region']][container['name']]['bytes'] = container['bytes']
					try:
						old_usage['object-store'][endpoint['region']].pop(container['name'])
					except ValueError:
						pass

					object_csv_data.append([endpoint['region'],container['name'],container['count'],container['bytes']])

					text += "%-15s %-25s %10s %10s %10s\n" % (endpoint['region'], container['name'], 
													container['count'], 
													sizeof_fmt(container['bytes']), 
													"$"+storage_price(container['bytes']))


		if entry['type'] == 'compute':

			text += "\nCompute\n--------------\n\n"
			text += "%-20s %-40s %7s %7s\n" % ("Region","Name", "Size", "$/month")
			for endpoint in entry['endpoints']:
				nova = novaclient.v1_1.client.Client(None,None,None,auth_url="")
				nova.set_management_url(endpoint['publicURL'])
				nova.client.auth_token = ca.creds['token']
				flavors = dict()
				for flavor in nova.flavors.list():
					flavors[unicode(flavor.id)] = dict()
					flavors[unicode(flavor.id)]["display"] = sizeof_fmt(flavor.ram*1048576)
					flavors[unicode(flavor.id)]["price"] = get_compute_price(flavor.ram)
					flavors[unicode(flavor.id)]["ram"] = flavor.ram
					flavors[unicode(flavor.id)]["name"] = flavor.name

				for server in nova.servers.list():
					try:
						oldserver = old_usage['compute'][endpoint['region']][str(server.id)]
					except KeyError:
						oldserver = None
					if not oldserver:
						changes['compute'][endpoint['region']][server.id]['size'] = flavors[server.flavor['id']]["ram"]
						changes['compute'][endpoint['region']][server.id]['name'] = server.name
						changes['compute'][endpoint['region']][server.id]['added'] = True
					else:
						try:
							old_usage['compute'][endpoint['region']].pop(str(server.id))
						except ValueError:
							pass

					compute_csv_data.append([endpoint['region'],str(server.id),str(server.name),flavors[server.flavor['id']]["name"],flavors[server.flavor['id']]["ram"]])

					usage['compute'][endpoint['region']][server.id]['size'] = flavors[server.flavor['id']]["ram"]
					usage['compute'][endpoint['region']][server.id]['name'] = server.name
					text += "%-20s %-40s %7s %7s\n" % (endpoint['region'], server.name,
																flavors[server.flavor['id']]["display"],
																"$"+compute_price(flavors[server.flavor['id']]["price"]))
	if object_csv_data:
		object_csv = StringIO.StringIO()
		object_csv_writer = csv.writer(object_csv)
		object_csv_writer.writerows([["region","container","objects","bytes"]])
		object_csv_writer.writerows(object_csv_data)
		csv_data = object_csv.getvalue()
		files.append({"file-name":"object-storage.csv","contents":csv_data})


	if compute_csv_data:
		compute_csv = StringIO.StringIO()
		compute_csv_writer = csv.writer(compute_csv)
		compute_csv_writer.writerows([["region","id","name","flavor","ram"]])
		compute_csv_writer.writerows(compute_csv_data)
		csv_data = compute_csv.getvalue()
		files.append({"file-name":"compute.csv","contents":csv_data})

	#print text
	ca.store(json.dumps(usage))

	changes_html = ""

	for dataset in [changes, old_usage]:
		for service, service_data in dataset.items():
			for zone, zone_data in service_data.items():
				for change, change_data in zone_data.items():
					if service == 'object-store':
						changes_html += "<tr><td>"+str(service)+"</td>"
						changes_html += "<td>"+str(zone)+"</td>"
						changes_html += "<td>"+str(change)+"</td><td>"
						if change_data.get("count"):
							if change_data['count'] > 0:
								changes_html += "<font color='green'>+"+str(change_data['count'])+" obj</font>"
							elif change_data['count'] < 0:
								changes_html += "<font color='red'>-"+str(change_data['count'])+" obj</font>"
						changes_html += "</td><td>"
						if change_data.get("bytes"):
							if change_data['bytes'] > 0:
								changes_html += "<font color='green'>+"+sizeof_fmt(change_data['count'])+"</font>"
							elif change_data['bytes'] < 0:
								changes_html += "<font color='red'>-"+sizeof_fmt(change_data['count'])+"</font>"
						changes_html += "</td></tr>\n"
					elif service == 'compute':
						if change_data.get('name'):
							changes_html += "<tr><td>"+str(service)+"</td>"
							changes_html += "<td>"+str(zone)+"</td>"
							changes_html += "<td>"+str(change_data.get('name'))+"</td><td colspan=2>"
							if change_data.get('added'):
								changes_html += "<font color='green'>Created "+sizeof_fmt(change_data['size']*1048576)+" server</font>"
							else:
								changes_html += "<font color='red'>Deleted "+sizeof_fmt(change_data['size']*1048576)+" server</font>"
							changes_html += "</td></tr>\n"



	if changes_html != '':
		changes_html = """
<table>
	<tr>
		<td><b>Service</b></td>
		<td><b>Zone</b></td>
		<td><b>Item</b></td>
		<td colspan=2><b>Change</b></td>
	</tr>
		""" + changes_html + """
</table>
		"""

		ca.email("Usage Change",text, changes_html, files)


def sizeof_fmt(num):
    for x in [' B','KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0
    return "%3.1f %s" % (num, 'TB')
	
def storage_price(num):
	return "%0.2f" % ((float(num)/1073741824.0)*0.1,)

def compute_price(hourly):
	return "%0.2f" % (float(hourly)*24.0*30.0,)

def get_compute_price(ram):
	ram = int(ram)
	if ram == 1024:
		return 0.035
	elif ram == 2048:
		return 0.07
	elif ram == 4096:
		return 0.14
	elif ram == 8192:
		return 0.28
	elif ram == 16384:
		return 0.56
	elif ram == 16384:
		return 1.12
	else:
		return 0.0

class AutoVivification(dict):
    """Implementation of perl's autovivification feature."""
    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value

#		ca.email("File missing: "+ca.conf['container']+"/"+path,'''
#	The container '%s' appears to be missing the file '%s'.
#	''' % (ca.conf['container'], path))
		

ca.run(agent)
