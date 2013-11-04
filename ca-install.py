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

import shutil
import os
import sys
import random
import argparse

if __name__ == '__main__':
	sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)


	parser = argparse.ArgumentParser(
		formatter_class=argparse.RawDescriptionHelpFormatter,
		description='''
This script installs the Cloud Agents developer environment.

Options:

	ubuntu	- Installs all dependencies for Ubuntu 12.04
	osx		- Installs all dependencies but MySQL for OSX 10.8
	config 	- Configs DBs and Creates Config File (OS Agnostic)

''')
	parser.add_argument('arguments', metavar='arguments', type=str, nargs='+',
		help="command")

	args = parser.parse_args()

# Read in our defaults

	if args.arguments[0] in ("ubuntu", "osx", "config"):

		print "Setting defaults and creating config file..."
		
		mysql_root_pass = ''.join(random.choice('0123456789abcdef') for i in range(8))
		mysql_agents_pass = ''.join(random.choice('0123456789abcdef') for i in range(8))	
		mysql_crypt_pass = ''.join(random.choice('0123456789abcdef') for i in range(8))

		substitutes = {}
		defaults = open("ca-sample-defaults.cfg")
		
		for line in defaults:
			if line[0] != "#" and "=" in line:
				(key,value) = line.split("=",1)
				key = key.strip()
				value = value.strip()
				substitutes[key] = value
		
		defaults.close()
		

	# Create our directories

		os.system("mkdir tmp")
		mypath = os.getcwd()
		substitutes['runner_agent_dir'] = mypath+"/tmp/"	
		substitutes['runner_lib_dir'] = mypath+"/agents/lib/"	
		substitutes['runner_fetcher_path'] = mypath+"/ca-fetcher.py"	
		substitutes['runner_fetcher_store_basepath'] = mypath+"/agents"	

		substitutes['api_db_pass'] = mysql_agents_pass
		substitutes['dispatch_db_pass'] = mysql_agents_pass
		substitutes['crypt_db_pass'] = mysql_crypt_pass

		config = open("ca-sample.cfg").read()

		for key in substitutes.keys():
			config = config.replace("*"+key+"*",substitutes[key])
		
		config_out = open("ca.cfg","w")
		config_out.write(config)
		config_out.close()
	
	if args.arguments[0] in ("ubuntu"):
	
		print "Installing CloudAgents python library system-wide in /usr/local/lib/python2.7/dist-packages/"

		os.system("""bash -c "sudo cp agents/lib/cloudagents.py /usr/local/lib/python2.7/dist-packages/" """)

		print "Updating APT..."
		
		os.system("""bash -c "sudo apt-get update" """)

		print "Installing MySQL..."
		
		print "MySQL Password: " + mysql_root_pass
		os.system("""bash -c "sudo debconf-set-selections <<< 'mysql-server-5.5 mysql-server/root_password password """+mysql_root_pass+"""'" """)
		os.system("""bash -c "sudo debconf-set-selections <<< 'mysql-server-5.5 mysql-server/root_password_again password """+mysql_root_pass+"""'" """)
		os.system("""bash -c "sudo apt-get -y install mysql-server libmysqlclient-dev" """)

	# Install python deps

		os.system("sudo apt-get -y install python-pip build-essential python-dev python-imaging")
		os.system("sudo easy_install -U distribute")
		os.system("sudo pip install MySQL-python PIL python-dateutil cython")
		os.system("sudo pip install SQLAlchemy pytz sendgrid-python bottle")
		os.system("sudo pip install python-swiftclient python-keystoneclient")
		os.system("sudo pip install python-novaclient ssh parsedatetime twython")
		os.system("wget https://github.com/surfly/gevent/archive/master.tar.gz")
		os.system("tar fxvz master.tar.gz")
		os.system("cd gevent-master; sudo python setup.py install")
		os.system("sudo rm -Rf gevent-master master.tar.gz")
	
	if args.arguments[0] in ("osx"):

		os.system("sudo easy_install -U distribute")
		print "Make sure you 'export DYLD_LIBRARY_PATH=/usr/local/mysql/lib/' before you run this, or MySQL won't work."
		os.system("sudo pip install MySQL-python PIL python-dateutil cython")
		os.system("sudo pip install SQLAlchemy pytz sendgrid-python bottle")
		os.system("sudo pip install python-swiftclient python-keystoneclient")
		os.system("sudo pip install python-novaclient ssh parsedatetime twython")
		os.system("wget https://github.com/surfly/gevent/archive/master.tar.gz")
		os.system("tar fxvz master.tar.gz")
		os.system("cd gevent-master; sudo python setup.py install")
		os.system("sudo rm -Rf gevent-master master.tar.gz")


	if args.arguments[0] in ("ubuntu", "osx", "config"):
	
		# Create MySQL DBs

		print "Creating MySQL Databases..."
		if args.arguments[0] in ("ubuntu"):
			os.system("mysqladmin -u root --password="+mysql_root_pass+" create agents")
			os.system("""mysql -u root --password='%s' agents -e 'GRANT ALL PRIVILEGES ON agents.* TO "agents"@"localhost" IDENTIFIED BY "%s";FLUSH PRIVILEGES;'""" % (mysql_root_pass, mysql_agents_pass))
			os.system("mysqladmin -u root --password="+mysql_root_pass+" create crypt")
			os.system("""mysql -u root --password='%s' crypt -e 'GRANT ALL PRIVILEGES ON crypt.* TO "crypt"@"localhost" IDENTIFIED BY "%s";FLUSH PRIVILEGES;'""" % (mysql_root_pass, mysql_crypt_pass))
		else:
			os.system("mysqladmin -u root create agents")
			os.system("""mysql -u root agents -e 'GRANT ALL PRIVILEGES ON agents.* TO "agents"@"localhost" IDENTIFIED BY "%s";FLUSH PRIVILEGES;'""" % (mysql_agents_pass))
			os.system("mysqladmin -u root create crypt")
			os.system("""mysql -u root crypt -e 'GRANT ALL PRIVILEGES ON crypt.* TO "crypt"@"localhost" IDENTIFIED BY "%s";FLUSH PRIVILEGES;'""" % (mysql_crypt_pass))


