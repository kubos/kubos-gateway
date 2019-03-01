import json
import logging
import sys

from kubos_gateway.gateway import Gateway
from kubos_gateway.tools.stream_tlm import TelemetryStreaming

if len(sys.argv) > 1:
    config_file = sys.argv[1]
else:
    config_file = 'config/config.local.json'

if len(sys.argv) > 2:
    mode = sys.argv[2]
else:
    mode = 'gateway'

with open(config_file, 'r') as configfile:
    # Allow "comments" in JSON for convenience.
    config = json.loads("\n".join([line for line in configfile if not line.startswith('/') or line.startswith('#')]))

Gateway.set_log_level(logging.DEBUG, very_verbose=True)

if mode == 'gateway':
    Gateway.run_forever(config)
elif mode == 'stream_tlm':
    TelemetryStreaming.run_forever(config)
