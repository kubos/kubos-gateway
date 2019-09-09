import asyncio
import time
import traceback
import logging
import toml

logger = logging.getLogger(__name__)


class KubOSSat:
    def __init__(self, name, sat_config_path):
        self.name = name
        self.sat_config_path = sat_config_path
        self.definitions = {
            "command_definitions_update": {
                "display_name": "Command Definitions Update",
                "description": "Retrieves the service information from the local config.toml and builds command definitions for each of the services within it.",
                "fields": []
            }
        }

    async def command_callback(self, command, gateway):
        try:
            output = "Command Completed"
            if command.type in self.definitions:
                if command.type == "command_definitions_update":
                    self.build_command_definitions()
                    asyncio.ensure_future(gateway.update_command_definitions(
                        system=self.name,
                        definitions=self.definitions))
                    output = f"Updated Definitions from config file: {self.sat_config_path}"
            else:
                asyncio.ensure_future(gateway.fail_command(
                    command_id=command.id, errors=[f"Invalid command type: {command.type}"]))

            asyncio.ensure_future(gateway.complete_command(
                command_id=command.id,
                output=output))
        except Exception as e:
            asyncio.ensure_future(gateway.fail_command(
                command_id=command.id, errors=[
                    "Command Failed to Execute. Unknown Error Occurred.", f"Error: {traceback.format_exc()}"]))

    def build_command_definitions(self):
        """Builds Command Definitions"""
        self.config = toml.load(self.sat_config_path)
        for service in self.config:
            if service in ["file-transfer-service"]:
                self.definitions["uplink_file"] = {
                    "display_name": "Uplink File",
                    "description": "Uplink a staged file to the spacecraft.",
                    "fields": [
                        {"name": "gateway_download_path", "type": "string"}
                    ]
                }
                self.definitions["downlink_file"] = {
                    "display_name": "Downlink File",
                    "description": "Downlink an image from the Spacecraft.",
                    "fields": [
                        {"name": "filename", "type": "string"},
                        {"name": "file-service-ip", "type": "string",
                            "value": self.config[service]["addr"]["ip"]},
                        {"name": "file-service-port", "type": "string",
                            "value": self.config[service]["addr"]["port"]}
                    ]
                }
            elif service in ["shell-service"]:
                self.definitions[service] = {
                    "display_name": "Shell Service Command",
                    "description": "Command to be executed using the shell service",
                    "fields": [
                        {"name": "ip", "type": "string",
                            "value": self.config[service]["addr"]["ip"]},
                        {"name": "port", "type": "string",
                            "value": self.config[service]["addr"]["port"]},
                        {"name": "shell-command", "type": "string"}
                    ]
                }
            else:
                self.definitions[service] = {
                    "display_name": service,
                    "description": f"GraphQL Request to the {service}",
                    "fields": [
                        {"name": "ip", "type": "string",
                            "value": self.config[service]["addr"]["ip"]},
                        {"name": "port", "type": "string",
                            "value": self.config[service]["addr"]["port"]},
                        {"name": "graphql-query", "type": "text", "default": "{ping}"}
                    ]
                }
