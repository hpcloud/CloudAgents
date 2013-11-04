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
from ssh import SSHClient, AutoAddPolicy, RSAKey
import random
import time
import StringIO
import urllib2
import re

ca = CloudAgent()

ca.required_config = {
	"name": "Apache Install",
	"version": "0.2.0",
	"credentials": True,
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This script creates a new VM and installs Apache 2 on it.""",
	"config":
		[{
			"name": "name",
			"regexp": "^.{1,50}$",
			"title": "Server Name",
			"description": "Name for the new server.",
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
			"name": "keypair",
			"regexp": "^.{1,50}$",
			"title": "Key Pair",
			"description": "Name of the existing keypair to use for the new server.",
			"type": "string",
			"required": True,
			"resource": "openstack.compute.[region].keypairs"
		},{
			"name": "flavor",
			"regexp": "^.{1,20}$",
			"title": "Flavor",
			"description": "Flavor/size of the server to create (ie: standard.xsmall).",
			"type": "string",
			"required": True,
			"resource": "openstack.compute.[region].flavors"
		},{
			"name": "secgroup",
			"regexp": "^.{1,40}$",
			"title": "Security Group",
			"description": "Security group to create the server in.",
			"type": "string",
			"required": True,
			"resource": "openstack.compute.[region].security-groups"
		},{
			"name": "software",
			"title": "CMS Software",
			"description": "CMS software to install on your server.",
			"type": "select",
			"required": True,
			"options": [
				{"name": "None", "value": "none", "default": True},
				{"name": "Wordpress", "value": "wordpress"},
				{"name": "Drupal", "value": "drupal"},
				]
		}
		]
	}

def run_command(command,regexp,ssh):
	"""
	Run a command, check our output, log a failure.
	"""
	stdin, stdout, stderr = ssh.exec_command(command)
	
	output = stdout.read()
	if regexp:
		if not re.match(regexp,output):
			ca.log_fail("Unexpected result from command, failing.",output)
			raise StandardError
	return output

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
	
	# Get the keypair we're supposed to insert.
	
	final_keypair = None
	
	for keypair in nova.keypairs.list():
		if keypair.name == ca.conf['keypair']:
			final_keypair = keypair
	
	if not final_keypair:
		ca.log_fail("Failing, keypair "+ca.conf['keypair']+" not found.")
		exit()
		
	ca.log("Found keypair.",'',2)
	
	# Get the flavor we're supposed to use.
	
	requested_flavor = None
	
	for flavor in nova.flavors.list():
		if flavor.name == ca.conf['flavor']:
			requested_flavor = flavor
	
	if not requested_flavor:
		ca.log_fail("Failing, flavor "+ca.conf['flavor']+" not found.")
		exit()
	
	ca.log("Found flavor.",'',3)
	

	# Get the image we're supposed to use.
	
	image_name = 'Ubuntu Precise 12.04 LTS Server 64-bit 20121026 (b)'
	
	for image in nova.images.list():
		if image.name == image_name:
			requested_image = image
	
	if not requested_image:
		ca.log_fail("Failing, image "+image_name+" not found.")
		exit()
	
	ca.log("Found image: "+requested_image.name+" ("+str(requested_image.id)+")",'',4)

	# Get the security group we're supposed to use.
	
	requested_group = None
	
	for group in nova.security_groups.list():
		if group.name == ca.conf['secgroup']:
			requested_group = group
	
	if not requested_group:
		ca.log_fail("Failing, group "+ca.conf['secgroup']+" not found.")
		exit()
	
	ca.log("Found group: "+requested_group.name+".",'',5)
		
	ca.log("Creating our temporary keypair.",'',6)
	
	my_keypair_name = ca.conf['keypair']+"-tempagent"+str(random.randint(0,999999999))
	my_keypair = nova.keypairs.create(my_keypair_name)


	ca.log("Starting server.",'',10)

	my_server = nova.servers.create(ca.conf['name'],
									requested_image,
									requested_flavor,
									security_groups=[requested_group.name],
									key_name=my_keypair_name)
	
	time.sleep(5)
	status = "working"
	c = 5
	server = nova.servers.get(my_server)
	while server.status != 'ACTIVE' or c > 120:
		server = nova.servers.get(my_server)
		time.sleep(1)
		c += 1
		
	if server.status != 'ACTIVE':
		ca.log_fail("Server didn't boot in 2 minutes.")
		nova.servers.delete(my_server)

	ca.log("Server created.",'',20)
	
	server_address = None
	for address in server.addresses['private']:
		if address['version'] == 4 and address['addr'][0:3] != '10.':
			server_address = address['addr']
	
	if not server_address:
		ca.log("Couldn't determine server address.")
		nova.keypairs.delete(my_keypair_name)
		nova.servers.delete(my_server)
		exit()

	try:

		private_key_file = StringIO.StringIO(my_keypair.private_key)
		
		key = RSAKey.from_private_key(private_key_file)
		
		
		ssh = SSHClient()
		ssh.set_missing_host_key_policy(AutoAddPolicy())
		
	except:
		print "Unexpected error:", sys.exc_info()[0], sys.exc_info()[1]

		
	ca.log("SSHing to server at "+server_address,'',30)

	time.sleep(5)
	c = 5
	
	while c < 180:
		try:
			ssh.connect(server_address, pkey=key, username='ubuntu', look_for_keys=False)
		
		except:
			time.sleep(5)
			c += 5
			continue
		
		break

	
	if c >= 180:
		ca.log_fail("Couldn't ssh in to server in 3 minutes.")
		nova.keypairs.delete(my_keypair_name)
		nova.servers.delete(my_server)
		exit()
	
	
	if ca.conf.get("software") == "none":
		
		
		ca.log("Connected to server, updating apt.",'',40)
		output = run_command("sudo apt-get update",None,ssh)
		ca.log("Connected to server, installing apache2.",output,50)
		output = run_command("sudo apt-get -y install apache2",None,ssh)
		ca.log("Installed apache2.",output,80)
		ca.log("Resetting temporary server keypair.",'',90)
		output = run_command("echo '"+final_keypair.public_key+"' > .ssh/authorized_keys",None,ssh)
		ca.log("Deleting temporary keypair.",'',95)
		nova.keypairs.delete(my_keypair_name)
	
	
		try:
			body = urllib2.urlopen("http://"+server_address+"/").read()
		except:
			ca.log("Server not found, something went wrong.")
			exit()
		
		ca.log("Server up at http://"+server_address+"/","Got:\n"+body,100)
		
	elif ca.conf.get("software") == "wordpress":
		
		ca.log("Connected to server, resetting temporary server keypair...",'',40)
		output = run_command("echo '"+final_keypair.public_key+"' > .ssh/authorized_keys",None,ssh)
		ca.log("Deleting temporary keypair.",'',45)
		nova.keypairs.delete(my_keypair_name)

		ca.log("Updating apt.",'',47)
		output = run_command("sudo apt-get update",None,ssh)
		ca.log("Installing apache 2 and php 5...",'',50)
		output = run_command("sudo apt-get install -y apache2 libapache2-mod-php5 php5-cli  php5-gd libssh2-php php5-curl",None,ssh)
		ca.log("Installed apache2.",output,60)
		ca.log("Installing mysql...",'',61)
		mysql_root_pass = ''.join(random.choice('0123456789abcdef') for i in range(8))
		mysql_wordpress_pass = ''.join(random.choice('0123456789abcdef') for i in range(8))
		output = run_command("sudo debconf-set-selections <<< 'mysql-server-5.5 mysql-server/root_password password "+mysql_root_pass+"'",None,ssh)
		output += run_command("sudo debconf-set-selections <<< 'mysql-server-5.5 mysql-server/root_password_again password "+mysql_root_pass+"'",None,ssh)
		output += run_command("sudo apt-get -y install mysql-server php5-mysql",None,ssh)
		ca.log("Installed mysql.",output,70)
		ca.log("Reconfiguring and reinstalling apache...",'',71)
		output = run_command("sudo ln -s /etc/apache2/mods-available/rewrite.load /etc/apache2/mods-enabled/",None,ssh)
		output += run_command("sudo sed -i 11's/None/All/' /etc/apache2/sites-enabled/000-default",None,ssh)
		output += run_command("sudo apachectl restart",None,ssh)
		ca.log("Restarted apache2.",output,75)
		ca.log("Creating mysql wordpress database...",'',76)
		output = run_command("mysqladmin -u root --password="+mysql_root_pass+" create wordpress",None,ssh)
		output += run_command("""mysql -u root --password='%s' wordpress -e 'GRANT ALL PRIVILEGES ON wordpress.* TO "wordpress"@"localhost" IDENTIFIED BY "%s";FLUSH PRIVILEGES;'""" % (mysql_root_pass, mysql_wordpress_pass),None,ssh)
		ca.log("Created mysql user.",output,80)
		ca.log("Downloading and installing wordpress...",'',81)
		output = run_command("wget http://wordpress.org/latest.tar.gz",None,ssh)
		ca.log("Downloaded wordpress.",output,85)
		ca.log("Expanding and configuring wordpress...",'',86)
		output = run_command("sudo rm -f /var/www/index.html",None,ssh)
		output += run_command("sudo tar fxvz latest.tar.gz -C /var/www/ --strip-components=1",None,ssh)
		output += run_command("sudo mkdir /var/www/wp-content/uploads",None,ssh)
		output += run_command("sudo chown -R ubuntu:www-data /var/www",None,ssh)
		output += run_command("sudo chmod g+w /var/www/wp-content/uploads",None,ssh)
		output += run_command("sudo touch /var/www/.htaccess",None,ssh)
		output += run_command("sudo chown ubuntu:www-data /var/www/.htaccess",None,ssh)
		output += run_command("sudo chmod g+w /var/www/.htaccess",None,ssh)
		output += run_command("cp /var/www/wp-config-sample.php /var/www/wp-config.php",None,ssh)
		output += run_command("sed -i 's/database_name_here/wordpress/g' /var/www/wp-config.php",None,ssh)
		output += run_command("sed -i 's/username_here/wordpress/g' /var/www/wp-config.php",None,ssh)
		output += run_command("sed -i 's/password_here/"+mysql_wordpress_pass+"/g' /var/www/wp-config.php",None,ssh)
		ca.log("Configured wordpress.",output,90)

		try:
			body = urllib2.urlopen("http://"+server_address+"/wp-admin/install.php").read()
		except:
			ca.log("Server not found, something went wrong.")
			exit()

		ca.log("Wordpress up at http://"+server_address+"/wp-admin/install.php, sending email.",'',95)

		ca.email("Apache 2 & Wordpress Setup on "+ca.conf['name']+" Complete","""
		Server setup complete.  Continue to web-based wordpress setup at:
		
		http://%s/wp-admin/install.php
		
		""" % (server_address))
		

		ca.log("Server up, activation email sent.",'',100)
		
	elif ca.conf.get("software") == "drupal":
		
		ca.log("Connected to server, resetting temporary server keypair...",'',40)
		output = run_command("echo '"+final_keypair.public_key+"' > .ssh/authorized_keys",None,ssh)
		ca.log("Deleting temporary keypair.",'',45)
		nova.keypairs.delete(my_keypair_name)

		ca.log("Updating apt.",'',47)
		output = run_command("sudo apt-get update",None,ssh)
		ca.log("Installing apache 2 and php 5...",'',50)
		output = run_command("sudo apt-get install -y apache2 libapache2-mod-php5 php5-cli  php5-gd libssh2-php php5-curl",None,ssh)
		ca.log("Installed apache2.",output,60)
		ca.log("Installing mysql...",'',61)
		mysql_root_pass = ''.join(random.choice('0123456789abcdef') for i in range(8))
		mysql_drupal_pass = ''.join(random.choice('0123456789abcdef') for i in range(8))
		drupal_admin_pass = ''.join(random.choice('0123456789abcdef') for i in range(8))
		output = run_command("sudo debconf-set-selections <<< 'mysql-server-5.5 mysql-server/root_password password "+mysql_root_pass+"'",None,ssh)
		output += run_command("sudo debconf-set-selections <<< 'mysql-server-5.5 mysql-server/root_password_again password "+mysql_root_pass+"'",None,ssh)
		output += run_command("sudo apt-get -y install mysql-server php5-mysql",None,ssh)
		ca.log("Installed mysql.",output,70)
		ca.log("Reconfiguring and reinstalling apache...",'',71)
		output = run_command("sudo ln -s /etc/apache2/mods-available/rewrite.load /etc/apache2/mods-enabled/",None,ssh)
		output += run_command("sudo sed -i 11's/None/All/' /etc/apache2/sites-enabled/000-default",None,ssh)
		output += run_command("sudo apachectl restart",None,ssh)
		ca.log("Restarted apache2.",output,75)
		ca.log("Creating mysql drupal database...",'',76)
		output = run_command("mysqladmin -u root --password="+mysql_root_pass+" create drupal",None,ssh)
		output += run_command("""mysql -u root --password='%s' drupal -e 'GRANT ALL PRIVILEGES ON drupal.* TO "drupal"@"localhost" IDENTIFIED BY "%s";FLUSH PRIVILEGES;'""" % (mysql_root_pass, mysql_drupal_pass),None,ssh)
		ca.log("Created mysql user.",output,80)
		ca.log("Downloading drush and drupal...",'',81)
		output = run_command("sudo apt-get install -y drush",None,ssh)		
		output += run_command("wget http://ftp.drupal.org/files/projects/drupal-7.22.tar.gz",None,ssh)
		ca.log("Downloaded drush and drupal.",output,85)
		ca.log("Configuring drupal...",'',86)
		output = run_command("sudo rm -f /var/www/index.html",None,ssh)
		output += run_command("sudo tar fxvz drupal-7.22.tar.gz -C /var/www/ --strip-components=1",None,ssh)
		output += run_command("sudo chown -R ubuntu:www-data /var/www",None,ssh)
		output += run_command("sudo sh -c 'cd /var/www ; drush site-install standard -y --db-url=mysql://drupal:"+mysql_drupal_pass+"@localhost/drupal --site-name=\""+ca.conf['name']+"\" --account-pass="+drupal_admin_pass+"'",None,ssh)
		output += run_command("sudo mkdir /var/www/sites/default/private",None,ssh)
		output += run_command("sudo mkdir /var/www/sites/default/private/files",None,ssh)
		output += run_command("sudo chown -R ubuntu:www-data /var/www/sites/default",None,ssh)
		output += run_command("sudo chmod 777 /var/www/sites/default/files",None,ssh)
		output += run_command("sudo chmod 777 /var/www/sites/default/private",None,ssh)
		output += run_command("sudo chmod 777 /var/www/sites/default/private/files",None,ssh)
		
		ca.log("Configured drupal, admin password: "+drupal_admin_pass,output,90)

		try:
			body = urllib2.urlopen("http://"+server_address+"/").read()
		except:
			ca.log("Server not found, something went wrong.")
			exit()

		ca.log("Drupal up at http://"+server_address+"/, sending email.",'',95)

		ca.email("Apache 2 & Drupal Setup on "+ca.conf['name']+" Complete","""
Server setup complete.  Login to your new drupal server at:
		
username: admin
password: %s
url:      http://%s/
		
		""" % (drupal_admin_pass,server_address))
		

		ca.log("Server up at http://"+server_address+"/ and activation email sent.",'',100)
		

ca.run(agent)
