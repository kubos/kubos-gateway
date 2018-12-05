# Development

First time:

1. Setup a virtualenv
```bash
virtualenv virtualenv -p `which python3`
source virtualenv/bin/activate
pip3 install --upgrade -r requirements.txt
```
1. Copy `config.json` to `config.local.json` and edit it.
1. For a server with basic auth endabled, set the websocket URL to something like `wss://username:password@staging.majortom.cloud/cable`

Every time:

```bash
source virtualenv/bin/activate
pip3 install --upgrade -r requirements.txt
python run.py
```

Deactivate virtualenv:

```bash
deactivate
```
