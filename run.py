import json
import logging
import sys
import argparse

from kubos_gateway.gateway import Gateway

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-c',
        '--config',
        help='Path to the config.local.json file, defaults to "config/config.local.json".',
        required=False)

    parser.add_argument(
        '-l',
        '--loglevel',
        help='Log level for the logger. Defaults to "debug", can be set to "info", or "error".',
        required=False)

    args = parser.parse_args()

    if args.config != None:
        config_filepath = args.config
    else:
        config_filepath = "config/config.local.json"

    with open(config_filepath, 'r') as configfile:
        # Allow "comments" in JSON for convenience.
        config = json.loads("\n".join([line for line in configfile if not line.startswith('/') or line.startswith('#')]))

    if args.loglevel == 'error':
        Gateway.set_log_level(logging.ERROR, very_verbose=False)
    elif args.loglevel == 'info':
        Gateway.set_log_level(logging.INFO, very_verbose=False)
    else:
        Gateway.set_log_level(logging.DEBUG, very_verbose=True)

    Gateway.run_forever(config)

if __name__ == "__main__":
    main()
