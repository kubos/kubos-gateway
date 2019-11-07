import asyncio
import time
import traceback
import logging
import toml
import json
import subprocess
import os
import datetime
import uuid
from kubos_sat import file_commands
from kubos_sat import shell_commands
from kubos_sat import graphql_commands

logger = logging.getLogger(__name__)


class KubosSat:
    def __init__(self, name, ip, sat_config_path, file_client_path=None, shell_client_path=None, file_list_directories=None, default_uplink_dir="/home/kubos/"):
        self.name = name
        self.ip = ip  # IP where KubOS is reachable. Overrides IPs in the config file.
        self.sat_config_path = sat_config_path
        self.config = toml.load(self.sat_config_path)
        self.file_client_path = file_client_path
        self.shell_client_path = shell_client_path
        self.definitions = {
            "command_definitions_update": {
                "display_name": "Command Definitions Update",
                "description": "Retrieves the service information from the local config.toml and builds command definitions for each of the services within it.",
                "fields": []
            }
        }
        self.file_list_directories = file_list_directories
        self.default_uplink_dir = default_uplink_dir

    async def cancel_callback(self, command_id, gateway):
        asyncio.ensure_future(gateway.cancel_command(command_id=command_id))

    async def command_callback(self, command, gateway):
        try:
            if command.type in self.definitions:
                if command.type == "command_definitions_update":
                    build_command_definitions.build(kubos_sat=self)
                    asyncio.ensure_future(gateway.update_command_definitions(
                        system=self.name,
                        definitions=self.definitions))
                    asyncio.ensure_future(gateway.complete_command(
                        command_id=command.id,
                        output=f"Updated Definitions from config file: {self.sat_config_path}"))
                elif command.type in self.config:
                    """GraphQL Request Command"""
                    graphql_commands.raw_graphql(
                        graphql=command.fields['graphql'],
                        ip=command.fields['ip'],
                        port=command.fields['port'],
                        command_id=command.id,
                        gateway=gateway)
                elif command.type == "uplink_file":
                    file_commands.uplink_file(kubos_sat=self, gateway=gateway, command=command)
                elif command.type == "downlink_file":
                    file_commands.downlink_file(kubos_sat=self, gateway=gateway, command=command)
                elif command.type == "update_file_list":
                    shell_commands.update_file_list(
                        kubos_sat=self, gateway=gateway, command=command)
                else:
                    asyncio.ensure_future(gateway.fail_command(
                        command_id=command.id,
                        errors=[f"Command execution is not implemented: {command.type}"]))
            else:
                asyncio.ensure_future(gateway.fail_command(
                    command_id=command.id,
                    errors=[f"Invalid command type: {command.type}"]))

        except Exception as e:
            asyncio.ensure_future(gateway.fail_command(
                command_id=command.id, errors=[
                    "Command Failed to Execute. Unknown Error Occurred.", f"Error: {traceback.format_exc()}"]))

    def build_command_definitions(self):
        """Builds Command Definitions"""
        self.config = toml.load(self.sat_config_path)
        for service in self.config:
            if service == "file-transfer-service":
                file_commands.build(kubos_sat=self, service=service)
            elif service == "shell-service":
                shell_commands.build(kubos_sat=self, service=service)
            else:
                graphql_commands.build(kubos_sat=self, service=service)
