# Cloud Agents

This is the source code for Cloud Agents, a prototype of a lightweight, pluggable OpenStack compatible orchestration and automation service.

## Features

Cloud Agents provides a REST compatible JSON-oriented API for scheduling, configuring and retrieving the status of provider supplied or user written Python agent scripts.  It also includes a simple web UI, allowing for easy browser scheduling and monitoring of task execution.  There is a cloudagents.py python module which turns scripts into Cloud Agents agents, a basic CLI, and a handful of sample agents which automate common cloud user tasks.  The start of developer documentation exists in docs/developer-overview.md.

## Architecture

Cloud Agents is made up of several components.  There's a front end API server, a Crypt server which does encryption and decryption, a dispatcher which distributes tasks, a runner which lives on one or more in-cloud servers, and a fetcher that downloads the users code.  These systems communicate over HTTP/HTTPS or database socket.  Any MySQL compatible database can be used for the central datastore.

## Installation

In addition to this source, you'll need some other bits of stuff to get a pretty, running install.

These include [Bootstrap](http://getbootstrap.com), [jQuery](http://jquery.org), and the [jQuery Validation Plugin](http://jqueryvalidation.org/).  More details are in web/public/note.txt

This service has a long dependency list, so I suggest you check out ca-install.py, which is designed for automated single-node installation on an Ubuntu VM, and INSTALL.txt, which walks through installation in an Ubuntu VM.