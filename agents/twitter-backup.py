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
import time
from datetime import datetime
from twython import Twython
from twython import TwythonError
from keystoneclient.v2_0 import client
import swiftclient
from operator import itemgetter
import json

ca = CloudAgent()

ca.required_config = {
	"name": "Twitter Backup",
	"version": "0.2.0",
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This script grabs tweets from twitter and saves them into object storage.""",
	"config":
		[{
			"name": "screen_name",
			"regexp": "^.{1,50}$",
			"title": "Screen Name",
			"description": "Twitter screen name to backup.",
			"type": "string",
			"required": True
		},{
			"name": "region",
			"regexp": "^.{1,50}$",
			"title": "Region",
			"description": "Short name for the object storage endpoint region to use (ie: region-a.geo-1).",
			"type": "string",
			"required": True,
			"resource": "openstack.object-store.endpoints.region"
		},{
			"name": "container",
			"regexp": "^.{1,50}$",
			"title": "Container",
			"description": "Name of the container to store backups in (ie: archive).",
			"type": "string",
			"required": True,
			"resource": "openstack.object-store.[region].containers"
		},{
			"name": "path",
			"regexp": "^.{1,250}$",
			"title": "File Path",
			"description": "Path to store the files under (ie: backup/tweets).",
			"type": "string",
			"required": True
		}
		]
	}

def agent():

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

	t = Twython()
	
	
	# Figure out what files already exist, and what our latest tweet is.
	
	files = []
	
	try:
		(headers,files) = swiftclient.get_container(region_endpoints['publicURL'],ca.creds['token'],
												ca.conf['container'],full_listing=True, prefix=ca.conf['path'])
	
	except swiftclient.client.ClientException:
		pass
	
	files = sorted(files, key=itemgetter('name')) 

	last_tweet = 0
	last_file = ''
	tweet_list = []
	
	if files:
		(headers,last_file) = swiftclient.get_object(region_endpoints['publicURL'],ca.creds['token'],
												ca.conf['container'],files[-1]['name'])
		headers = swiftclient.head_object(region_endpoints['publicURL'],ca.creds['token'],
												ca.conf['container'],files[-1]['name'])
		last_tweet = headers.get('x-object-meta-last-tweet-id',0)
		tweet_list = json.loads(last_file)
	
	# Grab our tweet list (tweets since last tweet up to 3200), optimized for
	# fewest requests.

	try:
		if last_tweet:
			tweets = t.getUserTimeline(screen_name=ca.conf['screen_name'], count=200, since_id=last_tweet, include_rts=True)
		else:
			tweets = t.getUserTimeline(screen_name=ca.conf['screen_name'], count=200, include_rts=True)

	except TwythonError, e:
		ca.log_fail("Error accessing twitter stream.  User not found or twitter down.")
		exit()
	
	if len(tweets) == 0:
		ca.log("No new tweets.")
		exit()
		
	tweet_list.extend(tweets)
	c = 200
	lowest_tweet = tweets[-1]['id']
	
	while tweets[-1]['id'] > last_tweet and c < 3200 and tweets:
		try:
			tweets = t.getUserTimeline(screen_name=ca.conf['screen_name'], max_id=tweets[-1]['id'], count=200, include_rts=True)
			if lowest_tweet == tweets[-1]['id']:
				break
			tweet_list.extend(tweets)
			c += 200
			ca.log("Grabbed "+str(len(tweets))+" starting at "+str(tweets[-1]['id']))
			lowest_tweet = tweets[-1]['id']
		except:
			break	
	
	# Combine with the last tweet storage file contents
	
	tweet_list = sorted(tweet_list, key=itemgetter('id')) 
	
	# Split into monthly files and save
	
	tweet_store = {'tweets': {},'mins':{},'maxes':{}}
	
	for tweet in tweet_list:
		time_struct = time.strptime(tweet['created_at'], "%a %b %d %H:%M:%S +0000 %Y")
		key = time.strftime("tweets-%Y%m.json",time_struct)
		if not tweet_store['tweets'].get(key):
			tweet_store['tweets'][key] = [tweet]
		else:
			tweet_store['tweets'][key].extend([tweet])
		if not tweet_store['mins'].get(key) or tweet_store['mins'].get(key) > tweet['id']:
			tweet_store['mins'][key] = tweet['id']
		if not tweet_store['maxes'].get(key) or tweet_store['maxes'].get(key) < tweet['id']:
			tweet_store['maxes'][key] = tweet['id']
	
	swiftclient.put_container(region_endpoints['publicURL'],ca.creds['token'],ca.conf['container'])
	
	for key in sorted(tweet_store['tweets']):
		ca.log("Storing file: "+ca.conf['container']+"/"+ca.conf['path']+"/"+key)
		swiftclient.put_object(region_endpoints['publicURL']+"/"+ca.conf['container']+"/"+ca.conf['path']+"/"+key, token=ca.creds['token'], contents=json.dumps(tweet_store['tweets'][key]), headers={"X-Object-Meta-First-Tweet-ID": tweet_store['mins'][key], "X-Object-Meta-Last-Tweet-Id": tweet_store['maxes'][key]})
	

ca.run(agent)
