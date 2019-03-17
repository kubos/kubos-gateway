# KubOS Python Gateway for Major Tom

*Note:* The gateway is currently in Beta, and is not well documented. 


# First time setup

1. Setup a virtualenv
```bash
pip3 install virtualenv
virtualenv virtualenv -p `which python3`
source virtualenv/bin/activate
pip3 install --upgrade -r requirements.txt
```
1. Copy `config.json` to `config.local.json` and edit it.
1. For a server with basic auth endabled, set the websocket URL to something like `wss://username:password@instance.majortom.cloud/gateway_api/v1.0`
1. For a local server, you won't want `wss`, since you don't have HTTPS running. Use something like `ws://localhost:3001/gateway_api/v1.0`

Every time:

```bash
source virtualenv/bin/activate
pip3 install --upgrade -r requirements.txt
python run.py
```

See `python run.py --help`

Deactivate virtualenv:

```bash
deactivate
```


# Usage

Specifying a config file to use:

```bash
python run.py config/config.local.json
```

Specifying a mode:

```bash
python run.py config/config.local.json gateway
python run.py config/config.local.json stream_tlm
```

Available modes:

* gateway
* stream\_tlm
