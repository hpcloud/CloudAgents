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
import novaclient
import swiftclient
from time import mktime
import datetime
import urllib2
import Image
import StringIO
import re
from collections import defaultdict
import ExifTags

ca = CloudAgent()

ca.required_config = {
	"name": "Image Gallery",
	"version": "0.1.0",
	"author": "Jeff Kramer",
	"url": "http://www.hpcloud.com/",
	"help": """This script looks for jpg/png files in a container, thumbnails them into another public container and creates html contact sheets for each directory.""",
	"config":
		[{
			"name": "region",
			"regexp": "^.{1,50}$",
			"title": "Region",
			"description": "Short name for the source object storage endpoint region.",
			"type": "string",
			"required": True,
			"resource": "openstack.object-store.endpoints.region"
		},{
			"name": "container",
			"regexp": "^.{1,50}$",
			"title": "Container",
			"description": "Name of the container to search for the source graphics in.",
			"type": "string",
			"required": True,
			"resource": "openstack.object-store.[region].containers"
		},{
			"name": "path",
			"regexp": "^.{1,250}$",
			"title": "Path",
			"description": "Path to search for jpgs under (ie: uploads/pictures/).",
			"type": "string",
			"required": False
		},{
			"name": "galleryregion",
			"regexp": "^.{1,50}$",
			"title": "Gallery Region",
			"description": "Short name for the object storage endpoint region.",
			"type": "string",
			"required": True,
			"resource": "openstack.object-store.endpoints.region"
		},{
			"name": "gallerycontainer",
			"regexp": "^.{1,50}$",
			"title": "Gallery Container",
			"description": "Name of the container to put the gallery in.",
			"type": "string",
			"required": True,
			"resource": "openstack.object-store.[region].containers"
		},{
			"name": "gallerypath",
			"regexp": "^.{1,250}$",
			"title": "Gallery Path",
			"description": "Subdirectory for the gallery (ie: gallery/).",
			"type": "string",
			"required": False
		},
		]
	}

def agent():
	
	ca.log("Starting!")
	
	keystone = client.Client(token=ca.creds['token'], tenant_id=ca.creds['tenantId'],
							auth_url=ca.creds['identity_url'])
	
	object_store_catalog = keystone.service_catalog.get_endpoints()['object-store']
	
	source_endpoint = None
	
	for endpoints in object_store_catalog:
		if endpoints['region'] == ca.conf['region']:
			source_endpoint = endpoints
	
	if not source_endpoint:
		ca.log_fail("Failing, source region not found in endpoint list.")
		exit()

	target_endpoint = None
	
	for endpoints in object_store_catalog:
		if endpoints['region'] == ca.conf['galleryregion']:
			target_endpoint = endpoints
	
	if not source_endpoint:
		ca.log_fail("Failing, target region not found in endpoint list.")
		exit()
	
	try:
		container = swiftclient.head_container(target_endpoint['publicURL'],ca.creds['token'],
												ca.conf['gallerycontainer'])
		if not '.r:*' in container.get('x-container-read'):
			ca.warn("Gallery container exists, but may not be publicly readable.","")
	except:
		ca.log("Gallery container doesn't exist, creating new publicly readable container.","")
		swiftclient.put_container(target_endpoint['publicURL'],ca.creds['token'],
												ca.conf['gallerycontainer'],{"X-Container-Read": ".r:*"})
	
	ca.log("Getting target listing.","")
	targetlisting = get_swift_container(target_endpoint['publicURL']+"/"+ca.conf['gallerycontainer']+"?prefix="+ca.conf.get('gallerypath'),ca.creds['token'])
	ca.log("Getting source listing.","")
	sourcelisting = get_swift_container(source_endpoint['publicURL']+"/"+ca.conf['container']+"?prefix="+ca.conf.get('path'),ca.creds['token'])
	
	good_files = re.compile(".*\.(JPG|jpg|JPEG|jpeg|PNG|png)$")
	something_changed = False
	
	# We should add some stuff to clean up paths, ie: ensure they end in a slash.  Later.
	for file in sourcelisting:
		if good_files.match(file):
			justfile = file.replace(ca.conf.get("path"), "")
			(name,ext) = justfile.rsplit(".",1)
			if not ca.conf.get("gallerypath")+name+"-large."+ext in targetlisting or not ca.conf.get("gallerypath")+name+"-small."+ext in targetlisting:
				something_changed = True
				ca.log("Scaling "+justfile+" to smaller sizes.","")
				rescale(
					{"url": source_endpoint['publicURL'],"container": ca.conf['container'],"name":ca.conf.get('path')+justfile},
					{"url": target_endpoint['publicURL'],"container": ca.conf['gallerycontainer'],"name":ca.conf.get('gallerypath')+name+"-large."+ext},
					{"url": target_endpoint['publicURL'],"container": ca.conf['gallerycontainer'],"name":ca.conf.get('gallerypath')+name+"-small."+ext},
					ca.creds['token'])
				targetlisting.append(ca.conf['gallerypath']+name+"-large."+ext)

	tree = {}
	subs = {}

	if something_changed:
		# Rebuild our templates.
		
		for file in sourcelisting:
			if good_files.match(file):
				name = file.replace(ca.conf.get("path"), "")
				path = name.split("/")
				if len(path) > 1:
					subpath = "/".join(path[:-1])
					if tree.get(subpath):
						tree[subpath].extend([path[-1]])
					else:
						tree[subpath] = [path[-1]]
											
				else:
					if tree.get(""):
						tree[""].extend(path)
					else:
						tree[""] = path

				if len(path) > 1:
					level_above = "/".join(path[0:-2])
					if subs.get(level_above):
						subs[level_above].add(path[-2])
					else:
						subs[level_above] = set([path[-2]])
	

		head = """
<head><title>%s Gallery</title>
<link href="//netdna.bootstrapcdn.com/twitter-bootstrap/2.1.1/css/bootstrap-combined.min.css" rel="stylesheet">
<link href="https://region-a.geo-1.objects.hpcloudsvc.com:443/v1.0/16026287679679/testcontainer/colorbox/colorbox.css" rel="stylesheet">
<script src="//ajax.googleapis.com/ajax/libs/jquery/1.8.1/jquery.min.js"></script>
<script src="//netdna.bootstrapcdn.com/twitter-bootstrap/2.1.1/js/bootstrap.min.js"></script>
<script src="http://cdn.jsdelivr.net/colorbox/1.3.19.3/jquery.colorbox-min.js"></script>
        <script>
			$(document).ready(function(){
                $('a.gallery').colorbox({ rel:'group1' });
            });
        </script>
<style>
.thumbnail { height: 150px, width: 150px }
</style>
</head>
<body>
<div class="container">
<h1>%s Gallery</h1>

	"""

		sublist = """
<h2>Sub-Galleries</h2>
<ul class="nav nav-tabs nav-stacked">
	"""
		back_up = """
<ul class="nav nav-tabs nav-stacked">
<li><a href="../">Back to %s</a></li>
</ul>	
"""

		gallery_top = """
<ul class="thumbnails">
	"""
	
		gallery_bottom = """
</ul>
	"""
		footer = """
</div>
</body>
	"""

		for name, template in tree.items():
			ca.log("Writing gallery template for "+name,"")
			pretty_name = name.split("/")[-1]
			
			html = head % (pretty_name,pretty_name)
			if name:
				if len(name.split("/")) == 1:
					html += back_up % ("Home")
				elif len(name.split("/")) > 1:
					html += back_up % (name.split("/")[-2])
				
			if subs.get(name):
				html += sublist
				for subpath in subs[name]:
					html += '<li><a href="%s/">%s</a></li>\n' % (subpath, subpath)
				html += "</ul>\n"
			
			html += gallery_top
			for file in template:
				(filename,extension) = file.rsplit(".",1)
				html += "<li class='span3'>\n<a href='%s' class='gallery thumbnail'><img src='%s'></a></li>\n" % (filename+"-large."+extension,filename+"-small."+extension)
			
			html += gallery_bottom
			html += footer
			
			filename = name
			if filename and filename[-1] != '/':
				filename = filename +"/"
			
			swiftclient.put_object(target_endpoint['publicURL']+"/"+ca.conf['gallerycontainer']+"/"+ca.conf.get('gallerypath')+filename,
									contents=html, content_type="text/html", token=ca.creds['token'])
			
			
		ca.log("Gallery updated at "+target_endpoint['publicURL']+"/"+ca.conf['gallerycontainer']+"/"+ca.conf.get('gallerypath'),"")
	else:
		ca.log("No new files found.","")
	
	
def rescale(source,largethumb,smallthumb,token):
	"""
	Resize a given graphic from a source size to a smaller size.
	"""
	(headers,source_file) = swiftclient.get_object(source['url'],token,source['container'],source['name'])
	large_image_file = StringIO.StringIO(source_file)
	small_image_file = StringIO.StringIO(source_file)
	
	if source['name'].endswith("jpg") or source['name'].endswith("JPG") or source['name'].endswith("jpeg") or source['name'].endswith("JPEG"):
		type = "JPEG"
	elif source['name'].endswith("png") or source['name'].endswith("PNG"):
		type = "PNG"
	
	
	large = Image.open(large_image_file)
	small = Image.open(small_image_file)
	
	# This chunk rotates images if they have exif data that indicates that they need rotation.
	
	for orientation in ExifTags.TAGS.keys(): 
		if ExifTags.TAGS[orientation]=='Orientation':
			break 
	if hasattr(large, '_getexif'):
		e = large._getexif()
		if e is not None:
			exif=dict(e.items())
			orientation = exif[orientation] 
			if orientation == 3 : 
				large=large.transpose(Image.ROTATE_180)
				small=small.transpose(Image.ROTATE_180)
			elif orientation == 6 : 
				large=large.transpose(Image.ROTATE_270)
				small=small.transpose(Image.ROTATE_270)
			elif orientation == 8 : 
				large=large.transpose(Image.ROTATE_90)
				small=small.transpose(Image.ROTATE_90)
	
	large.thumbnail((800,800), Image.ANTIALIAS)
	small.thumbnail((150,150), Image.ANTIALIAS)
	largeoutput = StringIO.StringIO()
	large.save(largeoutput, format=type)
	largedata = largeoutput.getvalue()
	largeoutput.close()

	smalloutput = StringIO.StringIO()
	small.save(smalloutput, format=type)
	smalldata = smalloutput.getvalue()
	smalloutput.close()
	
	swiftclient.put_object(str(largethumb['url']+"/"+largethumb['container']+"/"+urllib2.quote(largethumb['name'])).encode('utf-8'),token=token,contents=largedata)
	swiftclient.put_object(str(smallthumb['url']+"/"+smallthumb['container']+"/"+urllib2.quote(smallthumb['name'])).encode('utf-8'),token=token,contents=smalldata)
		
def get_swift_container(url,token,max=100000):
	"""
	Returns a list of files in a specific container.
	Pass in max if you want to return an error if there
	are more than a set number of files in the container.
	A 100,000 item list will likely take 20-30 meg of ram.
	"""
	
	files = []
	while True:
		if len(files):
			request = urllib2.Request(url+"&marker="+urllib2.quote(files[-1]),None, {'X-Auth-Token':token})
			try:
				response = urllib2.urlopen(request)
			except urllib2.HTTPError, e:
				return files

			file_list = response.read().splitlines()
			
		else:
			request = urllib2.Request(url,None, {'X-Auth-Token':token})
			try:
				response = urllib2.urlopen(request)
			except urllib2.HTTPError, e:
				return []

			file_list = response.read().splitlines()
		
		
		files += file_list
		if len(files) >= max:
			raise StandardError

		if len(file_list) < 10000:
			file_list = None
			break
		
	return files	

ca.run(agent)
