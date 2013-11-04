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

from fabric.api import run, env, hosts, sudo
from fabric.context_managers import cd
from fabric.operations import put
from time import sleep
import ConfigParser

config = ConfigParser.RawConfigParser()
config.read('fabric.cfg')

local_path = config.get('Deploy','local_path')
api_servers = config.get('Deploy','api_servers').split(",")
api_server_username = config.get('Deploy','api_server_username')
api_key = config.get('Deploy','api_key')
api_remote_path = config.get('Deploy','api_remote_path')

dispatch_servers = config.get('Deploy','dispatch_servers').split(",")
dispatch_server_username = config.get('Deploy','dispatch_server_username')
dispatch_key = config.get('Deploy','dispatch_key')
dispatch_remote_path = config.get('Deploy','dispatch_remote_path')

crypt_servers = config.get('Deploy','crypt_servers').split(",")
crypt_server_username = config.get('Deploy','crypt_server_username')
crypt_key = config.get('Deploy','crypt_key')
crypt_remote_path = config.get('Deploy','crypt_remote_path')

web_servers = config.get('Deploy','web_servers').split(",")
web_server_username = config.get('Deploy','web_server_username')
web_key = config.get('Deploy','web_key')
web_remote_path = config.get('Deploy','web_remote_path')

exe_servers = config.get('Deploy','exe_servers').split(",")
exe_server_username = config.get('Deploy','exe_server_username')
exe_key = config.get('Deploy','exe_key')
exe_remote_path = config.get('Deploy','exe_remote_path')

@hosts(api_servers)
def api():
	env.key_filename = api_key
	env.user = api_server_username
	put(local_path+"/ca-api.py",api_remote_path+"/ca-api.py")
	output = run("ps ax | grep 'ca-api\.' | grep Sl | awk '{print $1}'")
	if output:
		run("kill -TERM "+" ".join(output.split("\n")))
		sleep(2)
	with cd(api_remote_path):
		# This is... needlessly irritating.  For more insight into why
		# this sleeps, check out the following url:
		# https://github.com/fabric/fabric/issues/395
		run('nohup ./ca-api.py >> ca-api.log 2>&1 < /dev/null & sleep .5; exit 0')


@hosts(dispatch_servers)
def dispatch():
	env.key_filename = dispatch_key
	env.user = dispatch_server_username
	put(local_path+"/ca-dispatch.py",dispatch_remote_path+"/ca-dispatch.py")
	put(local_path+"/ca-alert-email.html",dispatch_remote_path+"/ca-alert-email.html")
	put(local_path+"/ca-alert-email.txt",dispatch_remote_path+"/ca-alert-email.txt")
	output = run("ps ax | grep 'ca-dispatch\.' | grep python | awk '{print $1}'")
	if output:
		run("kill -TERM "+" ".join(output.split("\n")))
		sleep(2)
	with cd(dispatch_remote_path):
		# This is... needlessly irritating.  For more insight into why
		# this sleeps, check out the following url:
		# https://github.com/fabric/fabric/issues/395
		run('nohup ./ca-dispatch.py >> ca-dispatch.log 2>&1 < /dev/null & sleep .5; exit 0')


@hosts(crypt_servers)
def crypt():
	env.key_filename = crypt_key
	env.user = crypt_server_username
	put(local_path+"/ca-crypt.py",api_remote_path+"/ca-crypt.py")
	output = run("ps ax | grep 'ca-crypt\.' | grep Sl | awk '{print $1}'")
	if output:
		run("kill -TERM "+" ".join(output.split("\n")))
		sleep(2)
	with cd(crypt_remote_path):
		# This is... needlessly irritating.  For more insight into why
		# this sleeps, check out the following url:
		# https://github.com/fabric/fabric/issues/395
		run('nohup ./ca-crypt.py >> ca-crypt.log 2>&1 < /dev/null & sleep .5; exit 0')

@hosts(web_servers)
def web():
	env.key_filename = web_key
	env.user = web_server_username
	put(local_path+"/web/ca-web.py",web_remote_path+"/web/ca-web.py")
	put(local_path+"/web/ca-web-sample.cfg",web_remote_path+"/web/ca-web-sample.cfg")
	put(local_path+"/web/templates",web_remote_path+"/web")
	put(local_path+"/web/public",web_remote_path+"/web")
	output = run("ps ax | grep 'ca-web\.' | grep Sl | awk '{print $1}'")
	if output:
		run("kill -TERM "+" ".join(output.split("\n")))
		sleep(2)
	with cd(web_remote_path+"/web"):
		# This is... needlessly irritating.  For more insight into why
		# this sleeps, check out the following url:
		# https://github.com/fabric/fabric/issues/395
		run('nohup ./ca-web.py >> ca-web.log 2>&1 < /dev/null & sleep .5; exit 0')

@hosts(exe_servers)
def runner():
	env.key_filename = exe_key
	env.user = exe_server_username
	put(local_path+"/ca-runner.py",exe_remote_path+"/ca-runner.py")

	# Terminate all our running agents.

	output1 = run("ps ax | grep 'agent\.' | awk '{print $1}'")
	if output1:
		sudo("kill -TERM "+output1.replace("\r"," ").replace("\n"," "))

	output2 = run("ps ax | grep 'ca-fetcher\.' | awk '{print $1}'")
	if output2:
		run("kill -TERM "+output2.replace("\r"," ").replace("\n"," "))

	output3 = run("ps ax | grep 'ca-runner\.' | grep Sl | awk '{print $1}'")
	if output3:
		run("kill -TERM "+output3.replace("\r"," ").replace("\n"," "))
		sleep(2)

	with cd(exe_remote_path):
		run('nohup ./ca-runner.py >> ca-runner.log 2>&1 < /dev/null & sleep .5; exit 0')

@hosts(exe_servers)
def exe():
	env.key_filename = exe_key
	env.user = exe_server_username
	put(local_path+"/ca-runner.py",exe_remote_path+"/ca-runner.py")
	put(local_path+"/ca-runner-setup.py",exe_remote_path+"/ca-runner-setup.py")
	put(local_path+"/ca-fetcher.py",exe_remote_path+"/ca-fetcher.py")
	put(local_path+"/agents",exe_remote_path)

	# Build it.

	with cd(exe_remote_path):
		run('python ca-runner-setup.py build')

	# Terminate all our running agents.

	output1 = run("ps ax | grep 'agent\.' | awk '{print $1}'")
	if output1:
		sudo("kill -TERM "+output1.replace("\r"," ").replace("\n"," "))

	output2 = run("ps ax | grep 'ca-fetcher\.' | awk '{print $1}'")
	if output2:
		run("kill -TERM "+output2.replace("\r"," ").replace("\n"," "))

	output3 = run("ps ax | grep 'ca-runner\.' | grep Sl | awk '{print $1}'")
	if output3:
		run("kill -TERM "+output3.replace("\r"," ").replace("\n"," "))
		sleep(2)

	with cd(exe_remote_path):
		run('python ca-runner-setup.py install')
		run('nohup ./ca-runner.py >> ca-runner.log 2>&1 < /dev/null & sleep .5; exit 0')

@hosts(api_servers)
def tail_api():
	env.key_filename = api_key
	env.user = api_server_username
	with cd(api_remote_path):
		run("tail -f ca-api.log")

@hosts(dispatch_servers)
def tail_dispatch():
	env.key_filename = dispatch_key
	env.user = dispatch_server_username
	with cd(api_remote_path):
		run("tail -f ca-dispatch.log")

@hosts(crypt_servers)
def tail_crypt():
	env.key_filename = crypt_key
	env.user = crypt_server_username
	with cd(crypt_remote_path):
		run("tail -f ca-crypt.log")

@hosts(web_servers)
def tail_web():
	env.key_filename = web_key
	env.user = web_server_username
	with cd(web_remote_path+"/web"):
		run("tail -f ca-web.log")

@hosts(exe_servers)
def tail_exe():
	env.key_filename = exe_key
	env.user = exe_server_username
	with cd(exe_remote_path):
		run("tail -f ca-runner.log")


