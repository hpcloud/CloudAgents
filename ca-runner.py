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
import re
import gevent.subprocess
import random
import os
import sys
import ConfigParser
import shutil
import errno
import signal


@route('/', method='GET')
def index():
	return "Pasta for baby!"

@route('/', method='POST')
def run_task():
	"""
	Run a Cloud Agents task.
	POST format:
	{
		"credentials": {
			"token": "OSTOKEN",
			"identity_url": "https:\/\/region-a.geo-1.identity.hpcloudsvc.com:35357\/v2.0\/",
			"tenantId": "TENANTID"
		},
		"agent_url": "swift://region-a.geo-1/mycontainer/myfile.py",
		"config": {
			"variable": "value"
		},
		"action": "validate"
	}
	"""

	process = str(random.randint(randmin,randmax))
	while os.path.isdir(agentdir+process):
		process = str(random.randint(randmin,randmax))
	

	post = json.loads(request.body.read())
	print "Running",post['action'],"for agent",post['agent_url']
	
	if not post.get('credentials'):
		yield log("Credentials missing.","","sys")
		return
	
	if not post.get('config') and post.get('config') != {}:
		yield log("Config missing.","","sys")
		sys.exit(errno.EACCES)
		
	if not post.get('agent_url'):
		yield log("Agent url missing.","","sys")
		sys.exit(errno.EACCES)

	if not post.get('action'):
		yield log("Action missing.","","sys")
		sys.exit(errno.EACCES)

	validation = {
			"token": "^.+$",
			"identity_url": "^.+$",
			"tenantId": "^.+$",
		}

	if not validate_dict(post['credentials'], validation):
		yield log("Validation error, credentials JSON didn't match required format: " + str(validation),"","sys")
		return


	fetcher_json = post['credentials']
	fetcher_json['agent_url'] = post['agent_url']
	ext = post['agent_url'].split(".")[-1]

	if chroot_process:
		agent_file = tmp_sub_path+"/"+process+"/agent."+ext
	else:
		agent_file = agentdir+process+"/agent."+ext

	if post['agent_url'][0:4] == 'file':
		if not re.match("^file\:\/\/\/.+$",post['agent_url']):
			yield log("File path invalid.","","fail")
			return
		else:
			fetcher_json['agent_url'] = "file://"+fetcher_store_basepath+ \
										fetcher_json['agent_url'][7:]




	fetcher_json['filename'] = agent_file
	
	agent_json = {}
	agent_json['config'] = post['config']
	agent_json['service'] = post['service']
	agent_json['credentials'] = post['credentials']
	if post.get('datastore'):
		agent_json['datastore'] = post['datastore']

	yield log("Fetching agent from "+post['agent_url']+".")

	if chroot_process:

		os.system("sudo mkdir "+slug_tmp_mount+"/"+process)
		os.system("sudo chown "+process+":"+process+" "+slug_tmp_mount+"/"+process)

		fetcher_cmd = "sudo chroot --userspec="+process+":"+process+" "+slug_mount+""" bash -i -c  "ulimit -u 4 -v 100000 -m 100 -t 30; """+fetcher_path+""" " """
		fetcher = gevent.subprocess.Popen(fetcher_cmd, shell=True,stdout=gevent.subprocess.PIPE, stderr=gevent.subprocess.PIPE, stdin=gevent.subprocess.PIPE)
		fetcher.stdin.write(json.dumps(fetcher_json))
		fetcher.stdin.close()


	else:
		os.mkdir(agentdir+process)

		fetcher = gevent.subprocess.Popen(fetcher_path, shell=True,stdout=gevent.subprocess.PIPE, stderr=gevent.subprocess.PIPE, stdin=gevent.subprocess.PIPE)
		fetcher.stdin.write(json.dumps(fetcher_json))
		fetcher.stdin.close()


	while True:
		nextline = fetcher.stdout.readline()
		if nextline == '' and fetcher.poll() != None:
			break
		#sys.stdout.write(nextline)
		#sys.stdout.flush()
		sleep()

	exitCode = fetcher.returncode

	if chroot_process:
		os.system("sudo chmod -R 500 "+slug_tmp_mount+"/"+process)

	
	if (exitCode != 0):
		yield log("Couldn't retrieve agent.","",None,"fail")
		print "File not found:",post['agent_url']

		return

	yield log("Running agent in "+process+".")

	if ext == 'py':
		# We're running a python script.
		if post['action'] == 'validate':
			args = '-v'
		elif post['action'] == 'config':
			args = '-c'
		else:
			args = '-j'


		if chroot_process:
			command = "sudo chroot --userspec="+process+":"+process+" "+slug_mount+""" bash -i -c  "ulimit -v 100000 -m 100; python -u """ + agent_file + " -i -j " +args+ """ " """

		else:
			command = ["/usr/bin/python","-u",agent_file,"-i","-j",args]
		
		agent = gevent.subprocess.Popen(command, shell=False,stdout=gevent.subprocess.PIPE, stderr=gevent.subprocess.PIPE, stdin=gevent.subprocess.PIPE)
		agent.stdin.write(json.dumps(agent_json))
		agent.stdin.close()

		global pids
		pids.add(agent.pid)


		while True:
			nextline = agent.stdout.readline()
			if nextline == '' and agent.poll() != None:
				break
			yield nextline
			#sys.stdout.flush()
			sleep()
		
		stderr = agent.stderr.read()

		exitCode = agent.returncode
		
		# Cleanup
		if chroot_process:
			os.system("sudo rm -Rf "+slug_tmp_mount+"/"+process)
		else:
			shutil.rmtree(agentdir+process,ignore_errors=True)

		pids.remove(agent.pid)

		if (exitCode != 0):
			yield log("Agent exited abnormally.",stderr,"note")
			yield log("Agent exited abnormally.",stderr,"fail")
			return
		else:
			print "Stderr for "+str(process)+": "
			print stderr
			yield log("Agent succeeded.")
			return

		

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
	return False


def log(title,message="",percent=None,type="sys"):
	"""
	Log message types:
	
	note  - general output
	sys   - system data
	fail - agent did not run as requested
	warn - agent running potentially harmfully
	"""
	return json.dumps({"title":title,"message":message,"type":type})+"\n"

def shutdown(*args):
	global pids
	print "Triggering Shutdown."
	while len(pids) > 0:
		sleep(1)
	exit()


if __name__ == "__main__":

	config = ConfigParser.RawConfigParser()
	config.read('ca.cfg')
	pids = set()

	agentdir = config.get('Runner','agent_dir')
	fetcher_path = config.get('Runner','fetcher_path')
	libdir = config.get('Runner','lib_dir')
	bind_address = config.get('Runner','bind_address')
	bind_port = config.get('Runner','bind_port')
	randmin = int(config.get('Runner','randmin'))
	randmax = int(config.get('Runner','randmax'))
	chroot_process = config.getboolean('Runner','chroot_process')
	fetcher_store_basepath = config.get('Runner','fetcher_store_basepath')
	slug_path = config.get('Runner','slug_path')
	slug_tmp_path = config.get('Runner','slug_tmp_path')
	slug_mount = config.get('Runner','slug_mount')
	slug_tmp_mount = config.get('Runner','slug_tmp_mount')
	tmp_sub_path = slug_tmp_mount[len(slug_mount):]

	signal.signal(signal.SIGTERM, shutdown)
	sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)


	run(host=bind_address, port=bind_port, server="gevent", debug=True)

	
