import asyncio
import time
import traceback
import logging
import toml
import requests
import json
import subprocess
import os
import datetime
import uuid
from kubos_sat.file_commands import FileCommands
from kubos_sat.build_command_definitions import BuildCommandDefinitions

logger = logging.getLogger(__name__)


class KubosSat:
    def __init__(self, name, ip, sat_config_path, file_client_path=None, shell_client_path=None, file_list_directories=None):
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
        self.file_commands = FileCommands(self)
        self.command_builder = BuildCommandDefinitions(self)

    async def cancel_callback(self, command_id, gateway):
        asyncio.ensure_future(gateway.cancel_command(command_id=command_id))

    async def command_callback(self, command, gateway):
        try:
            if command.type in self.definitions:
                if command.type == "command_definitions_update":
                    self.command_builder.build()
                    asyncio.ensure_future(gateway.update_command_definitions(
                        system=self.name,
                        definitions=self.definitions))
                    asyncio.ensure_future(gateway.complete_command(
                        command_id=command.id,
                        output=f"Updated Definitions from config file: {self.sat_config_path}"))
                elif command.type in self.config:
                    """GraphQL Request Command"""
                    self.graphql_command(
                        graphql=command.fields['graphql'],
                        ip=command.fields['ip'],
                        port=command.fields['port'],
                        command_id=command.id,
                        gateway=gateway)
                elif command.type == "uplink_file":
                    self.file_commands.uplink_file(gateway=gateway, command=command)
                elif command.type == "downlink_file":
                    self.file_commands.downlink_file(gateway=gateway, command=command)
                elif command.type == "shell-command":
                    asyncio.ensure_future(gateway.fail_command(
                        command_id=command.id,
                        errors=[f"Command not yet implemented"]))
                elif command.type == "update_file_list":
                    self.file_commands.update_file_list(gateway=gateway, command=command)
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
        self.command_builder.build()

    def graphql_command(self, graphql, ip, port, gateway, command_id):
        """GraphQL Request Command"""
        result = self.query(graphql=graphql, ip=ip, port=port)

        if 'errors' in result:
            logger.error(
                f"GraphQL Command Failed: {result['errors']}")
            asyncio.ensure_future(gateway.fail_command(
                command_id=command_id,
                errors=[f"GraphQL Request Failed: {result['errors']}"]))
        else:
            asyncio.ensure_future(gateway.complete_command(
                command_id=command_id,
                output=json.dumps(result)))

    def query(self, graphql, ip, port):
        """GraphQL Query"""
        logger.debug(graphql)
        url = f"http://{ip}:{port}/graphql"
        request = requests.post(
            url,
            json={
                'query': graphql
            })

        json_result = request.json()
        logger.debug(json.dumps(json_result, indent=2))
        return json_result
