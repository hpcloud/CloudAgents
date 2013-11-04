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

from sqlalchemy import Table, Column, Integer, Boolean, Text, DateTime, String, MetaData
from sqlalchemy import ForeignKey, create_engine, UniqueConstraint, select, func, desc, asc
from sqlalchemy.sql import text
from sqlalchemy.exc import IntegrityError

import json
import ConfigParser

import argparse
import subprocess
import os

if __name__ == '__main__':
	
	# Parse our arguments.
	
	parser = argparse.ArgumentParser(
		formatter_class=argparse.RawDescriptionHelpFormatter,
		description='''
This script updates the contents of the agents table in the CA database.

Sample commands:

Update Agents:	ca-populate-agents.py -d ./agents
''',
		epilog=''''''	)
	parser.add_argument('path', metavar='path', type=str, nargs=1,
		help="agent path")
	parser.add_argument('-d',dest='delete', action='store_true',
		help='delete all existing entries')
	parser.add_argument('-D',dest='drop', action='store_true',
		help='drop table and re-create')
	args = parser.parse_args()

	config = ConfigParser.RawConfigParser()
	config.read('ca.cfg')
	db_host = config.get('API','db_host')
	db_user = config.get('API','db_user')
	db_pass = config.get('API','db_pass')
	db_name = config.get('API','db_name')
	
	engine = create_engine('mysql://%s:%s@%s/%s?charset=utf8' % (db_user, db_pass, db_host, db_name))
	
	metadata = MetaData()
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
	
	if args.drop:
		agents.drop(engine)
		agents.create(engine)
	
	elif args.delete:
		engine.execute(agents.delete())
		
	for file in os.listdir(args.path[0]):
		ac = None
		if file[-3:] == ".py":
			print "Processing",file
			agent = subprocess.Popen([args.path[0]+"/"+file,"-c"], stdout=subprocess.PIPE)
			results = agent.stdout.read()
			try:
				ac = json.loads(results.encode('utf-8'))
			except TypeError, e:
				print "Json didn't validate"
				pass
			if ac:
				result = engine.execute(agents.insert(),
						agent_url="file:///"+file,
						name=ac['name'],
						author=ac['author'],
						version=ac['version'],
						url=ac['url'],
						help=ac['help'],
						config=json.dumps(ac['config'])
						)
				if result.rowcount:
					print "Inserted",ac['name'],ac['version'],"as",result.lastrowid
				else:
					print "Failed to insert"
					
			