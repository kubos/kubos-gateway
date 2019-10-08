# KubOS Python Gateway for Major Tom

*Note:* The gateway is currently in Beta, and is not well documented.
Please [submit an issue](https://github.com/kubos/kubos-gateway/issues/new) or
[come talk to us on Slack](https://slack.kubos.com) if you have any problems!

# First Time Setup

### Check Python Compatibility
The KubOS gateway requires Python 3.7+.
You can check your current version of Python by running:
`python --version` or `python3 --version` depending on your environment.
Whichever command (`python` or `python3`) results in a version that complies will be what you use for the rest of the command line instructions.
We will be using `python3` in the examples.

### Setup Python Virtualenv
Assuming you have the Gateway files on your machine, you'll need to run the following commands from the base folder of the Gateway:

```shell
pip3 install virtualenv
python3 -m venv virtualenv
source virtualenv/bin/activate
pip3 install --upgrade -r requirements.txt
```

### Setup Gateway Config File
Copy the contents of the `gateway_config.toml` into a new file titled `gateway_config.local.toml` and edit it appropriately.

### Retrieve Major Tom Connection Info
We highly recommend running it with the `-h` flag to see what all command line options are available:
```shell
python3 run.py -h
```
Most users will only need the Major Tom Hostname and Gateway Token.
Retrieve these from your instance of Major Tom.

# Running the Gateway
To run the Gateway, execute these commands,
replacing `{MAJOR TOM HOSTNAME}` and `GATEWAY TOKEN` as appropriate:

```shell
source virtualenv/bin/activate
python3 run.py {MAJOR TOM HOSTNAME} {GATEWAY TOKEN}
```

Example usage:

```shell
source virtualenv/bin/activate
python3 run.py app.majortom.cloud 16b9c3e2cb4b9faf3s252aa402985f5d2471f70304ada3efd673b411d1b7afes
```

After running the gateway, you can deactivate the virtualenv by running:
```shell
deactivate
```
