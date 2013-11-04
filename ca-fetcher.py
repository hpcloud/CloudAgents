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
import sys
from keystoneclient.v2_0 import client
import swiftclient
import urllib
import re
import shutil
import os

# Read our json.
data = sys.stdin.read()
try:
	json_data = json.loads(data)
except ValueError, e:
	sys.exit("Error parsing JSON!")

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
		print input
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
	print "String didn't match:",validate,"vs",input
	return False

validation = {
		'token' : "^\w+$",
		'identity_url' : "^.+\:\/\/.+\/.+$",
		'tenantId' : "^\w+$",
		'agent_url' : "^\w{3,5}\:\/\/[\w\-\.]{0,40}\/.{1,80}\.\w{1,5}$",
		'filename' : "^.+$",
	}

if not validate_dict(json_data, validation):
	exit("Validation error, input JSON didn't match required format: " + str(validation))

if json_data['agent_url'][0:4] == 'http':
	if urllib.urlretrieve(json_data['agent_url'], json_data['filename']):
		print "Success."
		sys.exit(0)
	else:
		sys.exit("Failed to download file.")
	
	
elif json_data['agent_url'][0:4] == 'file':
	path = json_data['agent_url'][7:]

	if os.path.exists(json_data['filename']):
		sys.exit("File already exists.")

	shutil.copyfile(path, json_data['filename'])
	if os.path.exists(json_data['filename']):
		print "Success."
		sys.exit(0)
	else:
		sys.exit("Failed to copy file.")
	
elif json_data['agent_url'][0:5] == 'swift':
	
	(method,trash,region,container,object_name) = json_data['agent_url'].split("/",4)
	
	keystone = client.Client(token=json_data['token'], tenant_id=json_data['tenantId'], auth_url=json_data['identity_url'])
	
	object_store_catalog = keystone.service_catalog.get_endpoints()['object-store']
	
	region_endpoints = None
	
	for endpoints in object_store_catalog:
		if endpoints['region'] == region:
			region_endpoints = endpoints
	
	if not region_endpoints:
		exit("Failing, region not found in endpoint list.")
	
	try:
		file = open(json_data['filename'],"w")
		headers, body = swiftclient.get_object(region_endpoints['publicURL'],json_data['token'],container,object_name,resp_chunk_size=65000)
		for chunk in body:
			file.write(chunk)
		file.close()
	
		print "Success."
		sys.exit(0)
	except swiftclient.client.ClientException, err:
		sys.exit("Failed to download agent file: "+err)
	
sys.exit("Failure.")