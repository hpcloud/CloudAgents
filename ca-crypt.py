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

from gevent import monkey, sleep; monkey.patch_all()
import json
from bottle import route, request, response, run
import ConfigParser
from Crypto.Cipher import AES
from Crypto import Random
from base64 import b64encode, b64decode
from sqlalchemy import Table, Column, String, MetaData, create_engine, Integer, select
import sys
import os


@route('/', method='GET')
def index():
	return "OSKJJ JGTMW"

@route('/v1.0/tenants/:tenant_id/encrypt', method='POST')
def encrypt(tenant_id="tenant_id"):
	"""
	Request an encryption run for the posted content.
	{
		"new_key": True,
		"values": {
			"identifier": "message",
			...
			}
	}
	new_key is optional.  If it's set, a new key is created to encrypt
	the data with.	
	"""
	try:
		post = json.loads(request.body.read())
	except:
		raise HTTPResponse(output="JSON unparseable.", status=400, header=None)
	
	# Do we need a new key?
	
	
	if post.get('new_key'):
		key = b64encode(Random.new().read(32))
		result = engine.execute(secretkeys.insert(), key=key, tenant_id=tenant_id)
		if not result.lastrowid:
			raise HTTPResponse(output="Unable to create new key.", status=400, header=None)
		id = result.lastrowid
	else:
		key_result = engine.execute(select([secretkeys], secretkeys.c.tenant_id==tenant_id))
		if key_result.rowcount > 0:
			keyrow = key_result.fetchone()
			key = keyrow.key
			id = keyrow.id
		else:
			key = b64encode(Random.new().read(32))
			result = engine.execute(secretkeys.insert(), key=key, tenant_id=tenant_id)
			if not result.lastrowid:
				raise HTTPResponse(output="Unable to create new key.", status=400, header=None)
			id = result.lastrowid

	values = {}


	if post.get("values"):
		for (identifier, message) in post.get("values").items():
		
			iv = Random.new().read(AES.block_size)
			cipher = AES.new(b64decode(key), AES.MODE_CFB, iv)
			#cipher.key_size = 32
			values[identifier] = storename+"-aes256-"+str(id)+"#"+ \
							b64encode(iv)+"|"+b64encode(cipher.encrypt(b64encode(message.encode('utf-8'))))
			
	return json.dumps({"values": values})			
	
	

@route('/v1.0/tenants/:tenant_id/decrypt', method='POST')
def decrypt(tenant_id="tenant_id"):
	"""
	Request an encryption run for the posted content.
	{
		"values": 
			{
				"identifier": "message",
				...
			}
	}	
	"""
	try:
		post = json.loads(request.body.read())
	except:
		raise HTTPResponse(output="JSON unparseable.", status=400, header=None)
	
	values = {}
	if post.get("values"):
		for (identifier, message) in post.get("values").items():
			style,data = message.split("#",1)
			storename,cypher,key_id = style.split("-",3)
			iv64,msg64 = data.split("|",1)
			key_result = engine.execute(select([secretkeys], secretkeys.c.id==key_id).where(secretkeys.c.tenant_id==tenant_id))
			if key_result.rowcount < 1:
				raise HTTPResponse(output="Key not found.", status=400, header=None)
			key = key_result.fetchone()
			decipher = AES.new(b64decode(key.key), AES.MODE_CFB, b64decode(iv64))
			
			values[identifier] = b64decode(decipher.decrypt(b64decode(msg64))).decode('utf-8')
			
	return json.dumps({"values": values})			
			

# We should probably implement recrypt at some point, to give the ability
# to cycle secretkeys without ever seeing the plaintext.  That's a problem for
# another day, though.




if __name__ == "__main__":

	config = ConfigParser.RawConfigParser()
	config.read('ca.cfg')

	db_host = config.get('Crypt','db_host')
	db_user = config.get('Crypt','db_user')
	db_pass = config.get('Crypt','db_pass')
	db_name = config.get('Crypt','db_name')
	storename = config.get('Crypt','storename')
	bind_address = config.get('Crypt','bind_address')
	bind_port = config.get('Crypt','bind_port')

	engine = create_engine('mysql://%s:%s@%s/%s' % (db_user, db_pass, db_host, db_name), pool_recycle=3600)

	metadata = MetaData()
	secretkeys = Table('secretkeys', metadata,
		Column('id', Integer, primary_key=True),
		Column('key', String(255)),
		Column('tenant_id', String(255), index=True)
	)

	# This won't overwrite if they already exist.
	metadata.create_all(engine)
	sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

	run(host=bind_address, port=bind_port, server="gevent")

	
