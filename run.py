import json
import logging
import sys

from kubos_gateway.gateway import Gateway

if len(sys.argv) > 1:
    config_file = sys.argv[1]
else:
    config_file = 'config/config.local.json'

with open(config_file, 'r') as configfile:
    # Allow "comments" in JSON for convenience.
    config = json.loads("\n".join([line for line in configfile if not line.startswith('/') or line.startswith('#')]))

if len(sys.argv) > 2:
    config["gateway-token"] = sys.argv[2]

Gateway.set_log_level(logging.DEBUG, very_verbose=False)
Gateway.run_forever(config)
