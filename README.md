# HookMan
HookMan is a web proxy that translate arbitrary webhooks between systems that require different request semantics. 
It is capable of mapping methods, URLs, and JSON bodies using Jinja templates. 
Although it should work for any system that generates WebHooks, HookMan was conceived to integrate Webhooks generated 
by NETSCOUT's Sightline product with various industry tools such as Slack and Discord.

## Operation

In operation, HookMan uses its configuration to export one or more endpoints. Each of these endpoints, when called by 
an incoming request will consult the configuration for that endpoint, transform the provided incoming data 
(e.g. from a Sightline Alert), and format an outgoing request with new semantics to match the service being called 
(e.g. a slack chat request). HookMan will then make that request to the outgoing service, and attempt to proxy back 
any status or error codes to the original caller.

Conceptually, it operates like this:

Calling Service ---> Hookman ---> Called Service

## Installation

### Requirements

HookMan will run in any environment that can supply a fully featured version of Python 3. 
It has been tested using Python version 3.7.2 but will likely work with anything later.
Any server providing this environment should work fine, including linux variants such as Ubuntu, MacOS etc. 
It has not been tested in a windows environment.

### Create a Virtual Environment

Although not strictly necessary, it is recommended that, as with any python package, it is installed in it's own virtual 
environment. If installed in the global environment it may result in the upgrade of specific python libraries which may 
in turn prevent other packages from running.

For full instructions on creation of Python Virtual Environments, please refer to the python docs:

https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/

As detailed in the docs, you may need to initially install the pip3 package manager as well as python's 
Virtual Environment module before you can actually create your virtual environment.

1. Create a top level directory for Hookman - this can be anywhere convenient such as in a home directory or elsewhere

```bash
$ mkdir hookman
$ cd hookman
```

2. Create the virtual environment.

```bash
$ python3 -m venv hookman_env
```

### Pull the package from the GitHub repository

Run a git clone command to grab the HookMan files from it's github repository.

From the top level directory:

```bash
https://github.com/arbor/HookMan.git
```

### Install Required Packages

From the top level directory:

1. Activate the virtual environment

```bash
$ source hookman_env/bin/activate
(hookman_env) $
```

(Note the change in prompt that shows that the virtual environment is now in use)

Install the requirements:

```bash
(hookman_env) $ pip3 install -r HookMan/requirements.txt
```

The hookman environment is now setup and is ready to run. Next we need to work on the configuration.

## The Mapping File

The mapping file is what hookman uses to configure the proxy and describe the various mappings that the proxy will 
support. It can support as many mappings as you need, with each mapping being accessed from a different HTTP
endpoint exported by the proxy, added in the configuration file.

Mapping files are in JSON format, and consist of 2 main sections

- A top level `http` section that provides configuration information
- a `mappings` section that configures all of the webhook mappings that will be supported

This example shows a complete mapping file with both sections shown:

```json
{
    "http":
    {
        "url": "http://192.168.1.20:9090"
    },
    "mappings":
    {
        "slack":
        {
            "method": "POST",
            "url": "<Slack URL>",
            "payload":
            {
                "text":"New Alert <{{payload['data']['id']}}>, type={{payload['data']['attributes']['alert_type']}}, misuse_types={{payload['data']['attributes']['subobject']['misuse_types']}}"
            }
        }
    }
}
```

### HTTP Section

The most important and only mandatory entry for the `HTTP` section is the `url` argument. For convenience this allows
the proxies endpoint to be specified as a URL, however the only part of the URL that is examined is the port, which is 
port that the proxy will listen on.

In the example above, the proxy will listen on port 9090.

TLS is supported, and if required can be enabled by adding argument for the SSL Certificate and key to the HTTP section. 
For example:

```json
{
    "http":
    {
        "url": "http://192.168.1.20:9090",
        "ssl_certificate": "path to SSL cert",
        "ssl_key": "path to SSL key"
    }
}
```

### Mapping Section

The `mappings` section is the heart of HookMan. It describes all of the mappings supported by this configuration and
how data is mapped from an incoming request to an outgoing request. Each entry in the `mappings` section describes an
endpoint that hookman will respond to, including the transformations that will be applied to the incoming data.

#### Mapping Entries

In the full example above, we see that the mappings section has one entry named `slack`. This means that HookMan will
export an endpoint named `slack` with a URL of:

```
http://<hookman IP>:<hookman port>/slack
``` 

The calling service is configured to make a call to the above URL, and when the incoming request is received, HookMan
will consult its mapping configuration to find the appropriate transformations and outgoing URL for the proxied
request.

#### Jinja Mapping

Under the covers, HookMan uses the Jinja2 templating language:

https://palletsprojects.com/p/jinja/

And although it barely scratches the surface of what jinja2 can do, it leaves the door open for very complex mappings 
if required. In most cases, the mappings will consist of pulling information from the incoming request and placing it 
appropriately in the outgoing request.

Jinja2 mapping are introduced by including variables in double braces:

```jinja2
{{some_variable}}
```

#### The Incoming Request

In the HookMan environment, when a mapping is being processed, the various parts of the incoming request are available
as Jinja 2 variables:

- `url` - parts of the incoming URL including arguments
- `headers` - incoming headers
- `payload `- a potentially complex structure that represents the payload of the incoming request 
(usually a JSON structure)

These 3 variables will be used in the mapping to substitute parts of the incoming request into the outgoing request 
as shown in the examples section below.

##### URL

The URL variable will contain the following fields extracted from the incoming request form the calling service:

- version - HTTP Version
- method - method used (e.g. `POST`)
- scheme - scheme (e.g. `http`)
- host: - host part of the URL (e.g. `127.0.0.1:9090`)
- remote - remote IP address
- path - path part of the URL (e.g. `/slack`)
- query: stringified version of a dict of the arguments (e.g. `"{'fred': '1', 'jim': '2'}"`)

##### Headers

The headers variable will consist of a dict of the header keys and values form the incoming request from the 
calling service. e.g.:

```python
{
    "Content-Type": 'application/json',
    "User-Agent": 'PostmanRuntime/7.26.1',
    "Accept": '*/*',
    "Cache-Control": 'no-cache'
}
```

##### Payload

The payload will consist of any JSON payload provided by the calling service (assuming a POST request), this will be
converted into python data structures.

#### The Outgoing Request

The outgoing request will consist of a mandatory `METHOD` and `URL` sections, along with optional `Headers` and `Payload` sections.

##### Method Section

The `method` section must exist and must be set to either `GET` or `POST`. For example:

```json
{
    "method": "POST"
}
```

##### URL Section

The URL section provides the URL of the called service. Most often this will be static, and often will be supplied
as part of the configuration of the integration. For instance, for Slack, creation of a new Slack APP results in
Slack supplying the creator with a full URL that will locate the correct Slack Server and Channel - this URL must be used verbatim. 

However, if it makes sense, it is possible to perform mappings on the outgoing URL to include information from the 
incoming request.

A static URL may be configured as follows:

```json
{
  "URL": "http://some.url.here/a/b/c"
}
```

An example of mapping something dynamic from the incoming payload might look like this:

```jinja2
{
    "URL": "http://some.url.here{{url[path]}}"
}
``` 

This would map the incoming path to the outgoing path (just an example, unlikely to be applicable in real life)

For services expecting `GET` requests, the `URL` is where you would add arguments, possibly containing mapped
data from the incming request.

##### Headers Section

The headers section allows for the configuration of any outgoing headers. This can be used to add authentication 
tokens, or anything else that the called service is expecting. Like the URL section, this can be static and will consist
of a JSON dictionary of keyword/values, but if required it is also possible to map information from the incoming
request into the headers section.

##### Payload Section

The payload section is what will be passed to the called service as JSON if a `POST` request is specified. 
The format of this section will be highly specific to the semantics required by the called service. 

In the example  below, we are creating a payload section that maps several parts of the calling server's payload to the 
outgoing payload, in order to create a line of text to be output by slack in one of it's channels (the incoming payload
is a Sightline Alert). This confirms to Slack's payload requirement for a single field called "text" containing the text 
to be output in the channel.

```jinja2
    "payload":
    {
        "text":"New Alert <{{payload['data']['id']}}>, type={{payload['data']['attributes']['alert_type']}}, misuse_types={{payload['data']['attributes']['subobject']['misuse_types']}}"
    }
```

An example output from the above, depending on the payload of the incoming alert from Sightline may look like this:

```jinja2
New Alert <2989061>, type=dos_host_detection, misuse_types=['UDP', 'DNS Amplification']
```

## Running HookMan

To run HookMan, first, make sure you are in the HookMan top level directory.

1. Activate the virtual environment if it is not already active.

```bash
$ source hookman_env/bin/activate
(hookman_env) $
```

(Note the change in prompt that shows that the virtual environment is now in use)

2. Run the hookman package:

```bash
$ cd HookMan
$ python3 -m hookman <path to mapping file>
```

Hookman will report any errors it finds in commandline parameters or in the mapping file, and if all is well, 
will loop forever waiting for requests, and a succesful startup will look something like this:

```bash
$ python3 -m hookman map.json
2020-07-13 11:30:15,312 INFO HookMan Version 0.1.0 starting
2020-07-13 11:30:15,312 INFO Configuration read from: /Users/acockburn/Development/hookman_test/hookman.json
2020-07-13 11:30:15,313 INFO Initializing HTTP
2020-07-13 11:30:15,313 INFO Running on port 9090
2020-07-13 11:30:15,314 INFO Start Main Loop
```

HookMan takes a few additional parameters, mainly useful for testing:

```bash
usage: hookman.py [-h] [-t] [-r] config

positional arguments:
  config        full or relative path to config file

optional arguments:
  -h, --help    show this help message and exit
  -t, --test    Test mode - print forwarding request and don't call
  -r, --reload  Reload config for every request - for testing purposes
```

## Examples

### Sightline to Slack

This map file will take an alert webhook from Sightline and reformat it to add a chat to a slack chat channel. 
Slack documentation details the required setup:

https://api.slack.com/messaging/webhooks

The process for setting up a webhook will result in the generation of a unique URL which should be substituted in 
the `url` field, and as you can see, requires a POST method and JSON payload with a field called `text`. In this case we have mapped various fields form the Sightline alert into the text field:

- Alert ID
- Alert Type
- Misuse Types

Here is the mapfile:

```json
{
    "http":
    {
        "url": "http://<ip>:<port>>"
    },
    "mappings":
    {
        "slack":
        {
            "method": "POST",
            "url": "<slack URL>",
            "payload":
            {
                "text":"New Alert <{{payload['data']['id']}}>, type={{payload['data']['attributes']['alert_type']}}, misuse_types={{payload['data']['attributes']['subobject']['misuse_types']}}"
            }
        }
    }
}

```

### Sightline to Discord

This map file will take an alert webhook from Sightline and reformat it to add a chat to a Discord chat channel. 
Discord documentation details the required setup:

https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks

The process for setting up a webhook will result in the generation of a unique URL which should be substituted in 
the `url` field, and as you can see, requires a POST method and JSON payload with a field called `content`. 
As in the previous example, we have mapped various fields form the Sightline alert into the text field:

- Alert ID
- Alert Type
- Misuse Types

Here is the mapfile:
```json
{
    "http":
    {
        "url": "http://<ip>:<port>"
    },
    "mappings":
    {
        "discord":
        {
            "method": "POST",
            "url": "<Discord URL>",
            "payload":
            {
                "content": "New Alert <{{payload['data']['id']}}>, type={{payload['data']['attributes']['alert_type']}}, misuse_types={{payload['data']['attributes']['subobject']['misuse_types']}}"
            }
        }
    }
}
```

## Contributions

Although we can make no promises to provide integrations with specific tools, we are happy to accept sample map files 
from anyone that has successfully integrated webhooks across systems using HookMan. 
To contribute a sample configuration simply create a Pull Request adding your sample to the `Exmples` section of this 
document, including a description of the source and destination system requirements, along with a sample JSON file in 
the examples directory.

## TODO

- Add digest authentication
- Support HTTP methods other than GET, POST

## Sightline Alert JSON

Since we are using Sightline alerts in the above examples, here is a quick example of a Sightline alert that we can map 
to other webhook semantics:

```json
{
  "meta": {
    "sp_version": "8.4",
    "api": "SP",
    "api_version": "4",
    "sp_build_id": "IDJG"
  },
  "data": {
    "relationships": {
      "packet_size_distribution": {
        "data": {
          "type": "alert_packet_size_distribution",
          "id": "packet-size-distribution-2989061"
        },
        "links": {
          "related": "https://cete.demo.arbor.net/api/sp/v4/alerts/2989061/packet_size_distribution"
        }
      },
      "thresholds": {
        "links": {
          "related": "https://cete.demo.arbor.net/api/sp/v4/alerts/2989061/misuse_types_thresholds/"
        }
      },
      "managed_object": {
        "data": {
          "type": "managed_object",
          "id": "463"
        },
        "links": {
          "related": "https://cete.demo.arbor.net/api/sp/v4/managed_objects/463"
        }
      },
      "source_ip_addresses": {
        "data": {
          "type": "alert_source_ip_addresses",
          "id": "source-ip-addresses-2989061"
        },
        "links": {
          "related": "https://cete.demo.arbor.net/api/sp/v4/alerts/2989061/source_ip_addresses"
        }
      },
      "patterns": {
        "links": {
          "related": "https://cete.demo.arbor.net/api/sp/v4/alerts/2989061/patterns/"
        }
      },
      "traffic": {
        "data": {
          "type": "alert_traffic",
          "id": "alert-traffic-2989061"
        },
        "links": {
          "related": "https://cete.demo.arbor.net/api/sp/v4/alerts/2989061/traffic"
        }
      },
      "device": {
        "data": {
          "type": "device",
          "id": "100"
        },
        "links": {
          "related": "https://cete.demo.arbor.net/api/sp/v4/devices/100"
        }
      },
      "annotations": {
        "data": [
          {
            "type": "alert_annotation",
            "id": "1604800"
          },
          {
            "type": "alert_annotation",
            "id": "1604797"
          },
          {
            "type": "alert_annotation",
            "id": "1604793"
          },
          {
            "type": "alert_annotation",
            "id": "1604787"
          }
        ],
        "links": {
          "related": "https://cete.demo.arbor.net/api/sp/v4/alerts/2989061/annotations/"
        }
      },
      "router_traffic": {
        "links": {
          "related": "https://cete.demo.arbor.net/api/sp/v4/alerts/2989061/router_traffic/"
        }
      }
    },
    "attributes": {
      "alert_type": "dos_host_detection",
      "classification": "Possible Attack",
      "importance": 2,
      "start_time": "2019-01-18T07:30:45+00:00",
      "alert_class": "dos",
      "ongoing": false,
      "stop_time": "2019-01-18T07:44:36+00:00",
      "subobject": {
        "direction": "Incoming",
        "impact_bps": 52766716,
        "impact_pps": 46727,
        "misuse_types": [
          "UDP",
          "DNS Amplification"
        ],
        "severity_threshold": 40000,
        "impact_boundary": "network",
        "severity_percent": 108.0,
        "ip_version": 4,
        "fast_detected": false,
        "host_address": "141.212.123.32",
        "severity_unit": "pps"
      }
    },
    "type": "alert",
    "id": "2989061",
    "links": {
      "self": "https://cete.demo.arbor.net/api/sp/v4/alerts/2989061"
    }
  },
  "links": {
    "self": "https://cete.demo.arbor.net/api/sp/v4/alerts/2989061"
  }
}
```
