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

import sys
import ConfigParser
import shutil
import os
import argparse

if __name__ == "__main__":

	parser = argparse.ArgumentParser(
		formatter_class=argparse.RawDescriptionHelpFormatter,
		description='''
This script creates and deploys the Cloud Agents worker slug.

Options:

	build	- Create a new slug with -tmp postfix
	install	- Unmount current slug and install new slug

''')
	parser.add_argument('arguments', metavar='arguments', type=str, nargs='+',
		help="command")

	args = parser.parse_args()

	# Read in our defaults

	config = ConfigParser.RawConfigParser()
	config.read('ca.cfg')

	agentdir = config.get('Runner','agent_dir')
	fetcher_path = config.get('Runner','fetcher_path')
	libdir = config.get('Runner','lib_dir')
	bind_address = config.get('Runner','bind_address')
	bind_port = config.get('Runner','bind_port')
	randmin = int(config.get('Runner','randmin'))
	randmax = int(config.get('Runner','randmax'))
	chroot_process = bool(config.get('Runner','chroot_process'))
	fetcher_store = config.get('Runner','fetcher_store')
	fetcher_store_basepath = config.get('Runner','fetcher_store_basepath')
	slug_path = config.get('Runner','slug_path')
	slug_tmp_path = config.get('Runner','slug_tmp_path')
	slug_mount = config.get('Runner','slug_mount')
	slug_tmp_mount = config.get('Runner','slug_tmp_mount')

	if args.arguments[0] in ("build"):

		print "Installing debootstrap"

		os.system("sudo apt-get -y install debootstrap")

				
		print "Creating slug fs"

		os.system("sudo umount -l "+slug_mount+"-tmp")
		os.system("sudo rm -f "+slug_path+"-tmp")
		os.system("sudo dd if=/dev/zero of="+slug_path+"-tmp bs=1024 count=1500000")
		os.system("sudo chmod 600 "+slug_path+"-tmp")
		os.system("sudo mkfs.ext3 -F "+slug_path+"-tmp")

		print "Creating slug tmp fs"

		os.system("sudo umount -l "+slug_tmp_mount+"-tmp")
		os.system("sudo rm -f "+slug_tmp_path+"-tmp")
		os.system("sudo dd if=/dev/zero of="+slug_tmp_path+"-tmp bs=1024 count=100000")
		os.system("sudo chmod 600 "+slug_tmp_path+"-tmp")
		os.system("sudo mkfs.ext3 -F "+slug_tmp_path+"-tmp")


		print "Mounting file system and installing bootstrap"

		os.system("sudo mkdir "+slug_mount+"-tmp")
		os.system("sudo mount "+slug_path+"-tmp "+slug_mount+"-tmp")
		os.system("sudo debootstrap --variant=buildd --arch i386 precise "+slug_mount+"-tmp http://archive.ubuntu.com/ubuntu")

		print "Populating slug"

		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "echo 'deb http://archive.ubuntu.com/ubuntu precise universe' >> /etc/apt/sources.list" """)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "apt-get update" """)

		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "apt-get -y install ca-certificates python-pip build-essential python-dev python-imaging libmysqlclient-dev wget" """)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "easy_install -U distribute" """)


		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "pip install MySQL-python PIL python-dateutil cython" """)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "pip install SQLAlchemy pytz sendgrid-python boto bottle" """)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "pip install python-swiftclient python-keystoneclient" """)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "pip install python-novaclient ssh parsedatetime twython" """)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "wget https://github.com/surfly/gevent/archive/master.tar.gz" """)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "tar fxvz master.tar.gz" """)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "cd gevent-master; python setup.py install" """)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "rm -Rf gevent-master master.tar.gz" """)
		os.system("sudo cp "+fetcher_store+"/lib/cloudagents.py "+slug_mount+"-tmp/usr/lib/python2.7/")
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "mkdir -p """+fetcher_store_basepath+""" " """)
		os.system("sudo cp "+fetcher_store+"/*.* "+slug_mount+"-tmp/"+fetcher_store_basepath)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "mkdir -p ca " """)
		os.system("""sudo chroot """+slug_mount+"""-tmp bash -c  "mkdir -p cell " """)
		os.system("sudo cp ca-fetcher.py "+slug_mount+"-tmp/ca")

		# Unmount our temp directories
		os.system("sudo umount -l "+slug_mount+"-tmp")
		os.system("sudo umount -l "+slug_tmp_mount+"-tmp")


	elif args.arguments[0] in ("install"):

		os.system("sudo mv "+slug_path+"-tmp "+slug_path)
		os.system("sudo mv "+slug_tmp_path+"-tmp "+slug_tmp_path)
		os.system("sudo umount -l "+slug_mount)
		os.system("sudo umount -l "+slug_tmp_mount)
		os.system("sudo mkdir "+slug_tmp_mount)

		os.system("sudo umount "+slug_mount)
		os.system("sudo mount -o ro "+slug_path+" "+slug_mount)
		os.system("sudo mount -o noexec,nodev "+slug_tmp_path+" "+slug_tmp_mount)
		os.system("sudo chmod go-r "+slug_tmp_mount)

