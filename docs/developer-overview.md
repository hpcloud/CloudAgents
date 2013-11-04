Cloud Agents Developer Documentation
====================================

Roads? Where we're going, we don't need roads.

- Doc Brown

Cloud Agents is a platform for running programs in the cloud, specifically the sort of little maintenance programs that make the world go round.  These programs have agency, they are designed to act on the cloud and the Internet at large on your behalf.  These programs, which we call agents, are configured with a set of options and a schedule into a task.  You may have many tasks, even many tasks using the same agent.  You may use agents provided by HP Cloud, created by the community, developed by someone for you or written yourself.  When the task runs, the Cloud Agents system acquires a token from keystone using a set of access keys you have stored in it, and gives them to the program.  The program then runs as if you were running it yourself.

In this phase all Agents are written in python, and are currently single file scripts.  Popular python libraries such as keystone, swiftclient, novaclient, boto and others can be available on the servers the agents execute on.

When agents run they can output messages, such as status updates, completion percentages, email notifications, and the like.  These messages are fed back into the agents central database, where they can be retrieved by the user or by other agents.

A Simple Agent
--------------

To develop agents all that is needed is the Cloud Agents python library and whatever libraries you plan to use.  The Cloud Agents library has no dependencies outside of the python standard library.

Lets take a look at a simple agent, one that just counts down to 0 to a number you specify.

    #!/usr/bin/env python
     
    import sys, os
    sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/lib')
     
    from cloudagents import CloudAgent
    from time import sleep

This is a fairly generic python script header, we're importing the CloudAgent class from the cloudagents library, and importing sleep from the time library. NOTE: We're using sys and os to append the /lib subdirectory in whatever directory you're in as a place to look for the cloudagents.py library. When in doubt, put it in there.

    ca = CloudAgent()

Here we've created a new ca object from our CloudAgent class. This ca object has some handy functions on it, which we'll explore later.

    ca.required_config = {
        "name": "Countdown Timer",
        "version": "0.1.0",
        "author": "Jeff Kramer",
        "url": "http://www.hpcloud.com/",
        "help": """This script counts down from count to 0, returning a message per second.""",
        "config":
            [{
                "name": "count",
                "regexp": "^\d+$",
                "title": "Count",
                "description": "Number to count down from.",
                "type": "string",
                "required": True
            }
            ]
        }

This chunk of code defines a dictionary on our ca object which sets our configuration and some friendly variables. Name is the name of your agent, version it's version, author who wrote it or is responsible for it, url should be a location where you can find out more about the agent, and help is a general description and introduction to using the agent.

The config chunk is where we define the options the agent has. It's a list of options, though in this case we only have one. Each configuration option has a name (what the script looks for when it's run), a title (a pretty name presented when the user sets it up), a description (to help the user in filling in the option), a type (string, boolean, or select list), whether the option is required, and for some options, a regular expression that can be used to validate that the input is correct.

    def agent():
     
        count = int(ca.conf['count'])
        for num in range(count,-1,-1):
            sleep(1)
            percent = 100-int((float(num)/float(count))*100.0)
            ca.log(str(num),"Counted down to "+str(num)+".",percent)

Now we define a function that is the core of what our agent does when it is run. In this case we're pulling in count (the configuration option we defined earlier in the config) and turning it into an integer. Then we count down from that number to 0, sleeping for one second at every step. We calculate how far through the countdown we are as a percentage, and then we use a ca helper function called log to send a message back to the agents system.

ca.log() take up to four arguments though we're only setting three here, they are: ca.log(title,message,percent,type). Titles are short chunks of text, the kind of thing you would put in a header or small area. Some examples may be 'Installing Software', 'Creating Keypair' or 'Checking for New Tweets'. Messages are where the debug or more extensive log output should go. They're also used for the message body when you request that an email be sent to a user. Feel free to dump command outputs or other longer chunks of text in there. Messages are optional. Percent is the completion percentage of the task, as an integer. Percent is optional. Type is only used when you want to send other kinds of messages back to the system, by default ca.log() assumes you're sending a note, which is a message left for the user to read.

    ca.run(agent)

This line requests that ca run our agent function. Before the agent function is run, ca validates the configuration. If the validation passes (based on the regular expressions and required settings you've created), the agent function is run, and then the agent is finished.

Agent Features
--------------

The Cloud Agents library gives you some command line options out of the box to make it easier to develop and debug agents.

Reading Input
-------------

Agents can read input one of two ways, you can feed a JSON formatted string into them. An example JSON config:

    {
    "config":
        {
            "count": "3"
        }
    }

Executed like this piping it into STDIN, assuming you stored the json config in a file called countdown.json:

    countdown.py -i < countdown.json

Or using the -f flag:

    countdown.py -f countdown.json

This should produce some output like this:

    $ ./countdown.py -i < countdown.json
    # 3
    Counted down to 3.
    # 2 (%34)
    Counted down to 2.
    # 1 (%67)
    Counted down to 1.
    # 0 (%100)
    Counted down to 0.
    $

The lines which start with # are titles. If the ca.log() command included a percentage, those are included in parenthesis. The lines below them are the messages.

To make development simpler, agents can also read their configuration interactively. Like this:

    countdown.py -I

The script should ask you for a number, and once you enter it, count down to 0. Try typing in something other than a number, or leaving it blank. I bet it doesn't work!

    $ ./countdown.py -I
    Number to count down from.
    Count: 3
    # 3
    Counted down to 3.
    # 2 (%34)
    Counted down to 2.
    # 1 (%67)
    Counted down to 1.
    # 0 (%100)
    Counted down to 0.
    $

When interacting with the rest of the system in production, the agents output JSON objects separated by newlines instead of pretty printed text. If you'd like to see what those look like, add the -j flag:

    $ ./countdown.py -I -j
    Number to count down from.
    Count: 3
    {"message": "Counted down to 3.", "type": "note", "title": "3"}
    {"type": "note", "message": "Counted down to 2.", "percent": 34, "title": "2"}
    {"type": "note", "message": "Counted down to 1.", "percent": 67, "title": "1"}
    {"type": "note", "message": "Counted down to 0.", "percent": 100, "title": "0"}
    $

If you'd like to just see the configuration without running the agent, you can use the -c flag:

    countdown.py -c

If you'd like to validate a configuration but not run the agent, pass in -v. (This doesn't work with interactive input.)

    countdown.py -v -f countdown.json

Interacting with the Cloud
--------------------------

Interacting with the rest of the cloud infrastructure is a core part of what agents are designed to do. The agents service generates a token for the owning user and passes it into each agent when it's executed. For simple agents like countdown these credentials aren't used, but for any advanced operations you'll probably want to have them. They're passed into the script in a JSON node called 'credentials'. A full agent configuration for an agent like the file existence checker would look like this:

    {
    "credentials":
        {
            "token": "HPAuth_0987654321",
            "identity_url": "https:\/\/region-a.geo-1.identity.hpcloudsvc.com:35357\/v2.0\/",
            "tenantId": "123456"
        },
    "config":
        {
            "container": "testcontainer",
            "region": "region-a.geo-1",
            "name": "backup/%Y-%m-%d.zip",
            "date": "-1 day"
        }
    }

For ease of development, instead of embedding this credentials node in your test configurations, you can either set environment variables with the data:

    $ export CA_TOKEN=HPAuth_0987654321
    $ export CA_TENANT_ID=123456
    $ export CA_IDENTITY_URL=https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/

Or set environment variables with a valid username/password or set of access keys, and have the HP Cloud Agents library request the token for you:

    $ export OS_USERNAME=jeff.kramer@hp.com
    $ export OS_PASSWORD=mypassword
    $ export OS_TENANT_ID=12345
    $ export OS_IDENTITY_URL=https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/

Or for a keypair:

    $ export OS_ACCESSKEY=1234567890
    $ export OS_SECRETKEY=0987654321
    $ export OS_TENANT_ID=12345
    $ export OS_IDENTITY_URL=https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/

Then run the agent with the -e flag if you've set the CA_TOKEN variables or the -E flag to use the OS variables and request a token for you.

Inside your script, you can then pass the token, tenant ID and identity url into standard open source OpenStack python libraries, such as this example from file_exists.py:

    keystone = client.Client(token=ca.creds['token'], tenant_id=ca.creds['tenantId'],
                            auth_url=ca.creds['identity_url'])

This line creates a new keystone object using the token, tenant ID and identity url that are present in ca.creds (as opposed to ca.config).

    object_store_catalog = keystone.service_catalog.get_endpoints()['object-store']

This line gets the object store endpoints for a user.

    region_endpoints = None
     
        for endpoints in object_store_catalog:
            if endpoints['region'] == ca.conf['region']:
                region_endpoints = endpoints
     
        if not region_endpoints:
            ca.log_fail("Failing, region not found in endpoint list.")
            exit()

This block works through every endpoint to see if it matches the config option 'region', if it does, that's the region the user requested. If it isn't, the script uses the ca.log_fail() function to note that it wasn't able to complete its task, and exits.

    if ca.conf.get('date'):
            c = pdc.Constants()
            p = pdt.Calendar(c)
            result = p.parse(ca.conf['date'])
            dt = datetime.datetime.fromtimestamp(mktime(result[0]))
            path = dt.strftime(ca.conf['name'])
        else:
            path = ca.conf['name']

This chunk of code does some fancy date parsing if the user has set a date modification.

    try:
            headers = swiftclient.head_object(region_endpoints['publicURL'],ca.creds['token'],
                                                    ca.conf['container'],path)
            if headers['content-length'] >= 0:
                ca.log("File exists!")
     
        except swiftclient.client.ClientException, e:
            ca.log("File doesn't exist!")
            ca.email("File missing: "+ca.conf['container']+"/"+path,'''
        The container '%s' appears to be missing the file '%s'.
        ''' % (ca.conf['container'], path))

This is the meat of the script, where it attempts to HEAD the file we asked it to check for (ca.conf'container' and ca.conf'name'). If the file doesn't exist, it logs that the file doesn't exist and uses the ca.email() helper function to request the system send an email to the user.

Datastore
---------

Each task has it's own private datastore, something that isn't visible via the API, but is intended to be a scratchpad for the task between runs. It's limited in size, encrypted when stored in the Cloud Agents service and designed as a place to store 'what was I working on' while the agent is inactive. An example of this is the countup.py agent which counts up from 0 or a number stored in the datastore by a configurable count every time it's run. It's a variation on countdown.py, so it should look similar.

    count = int(ca.conf['count'])
        if ca.datastore:
            start = int(ca.datastore)
        else:
            start = 0
     
        for i, num in enumerate(range(start+1,start+count+1,1)):
            sleep(1)
            percent = int((float(i+1)/float(count))*100.0)
            ca.log(str(num),"Counted up to "+str(num)+".",percent)
     
        ca.store(str(num))

countup.py initially checks to see if ca.datastore is set. If it isn't, this is likely a first run, so it starts at 0. If it is set, we've run before so it turns datastore into an integer. It then counts up like usual, logging each step. Once the counting is completed, it uses the new function ca.store() to store the number it counted to in the Cloud Agents database.

If you're testing an agent that uses the datastore in an environment where you don't have the Cloud Agents service, you can use a local file for a datastore by running the script with the -d option, like this:

    countup.py -I -d mynumber.txt

Try running this several times and see what happens, checking the contents of mynumber.txt each time.

You can store any string of reasonable length in the datastore, if you plan on dealing with complex character sets or binary data, we recommend base64 encoding it first so you can be sure that nothing is lost in transit.

Starting Points
---------------

If you'd like to create servers, move floating IPs, create keypairs, or other Nova-centric activities, look at server_resize.py.

If you'd like to upload files into swift or check if files exist look at image_gallery.py, file_exists.py, s3swiftsync.py, or twitter-backup.py.

If you'd like to see how to interact with external services, check out s3swiftsync.py and twitter-backup.py.

If you'd like to see how to SSH into a server and run commands, check out apache_install.py.

If you'd like to see how to schedule other tasks from an agent, check out relay.py. You can only really test and debug this kind of agent when you have access to the Cloud Agents service, for obvious reasons.
