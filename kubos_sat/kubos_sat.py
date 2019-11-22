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
from kubos_sat import graphql
from kubos_sat.shell_service import ShellService
from kubos_sat.file_service import FileService
from kubos_sat.app_service import AppService
from kubos_sat.exceptions import *

logger = logging.getLogger(__name__)


class KubosSat:
    def __init__(self, name, ip: str, sat_config_path: str, file_client_path=None, shell_client_path=None, file_list_directories=None, default_uplink_dir="/home/kubos/"):
        self.name = name
        self.ip = ip  # IP where KubOS is reachable. Overrides IPs in the config file.
        self.sat_config_path = sat_config_path
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
        self.app_service = None
        self.graphql_service_commands = []

    async def cancel_callback(self, command_id, gateway):
        asyncio.ensure_future(gateway.cancel_command(command_id=command_id))

    async def command_callback(self, command, gateway):
        try:
            if command.type not in self.definitions:
                raise CommandError(
                    command=command, message=f'Command: {command.type} is not defined in the Gateway. There is likely a mismatch between the Gateway and command definitions in Major Tom. Please issue the "Command Definitions Update" or "Retrieve Apps" command. Currently available commands are: {list(self.definitions.keys())}')

            if command.type == "command_definitions_update":
                self.build_command_definitions_command(gateway=gateway, command=command)
            elif command.type in self.graphql_service_commands:
                """Direct GraphQL Request Command"""
                graphql.graphql_command(gateway=gateway, command=command)
            elif command.type == "uplink_file":
                self.file_service.uplink_file(
                    kubos_sat=self, gateway=gateway, command=command)
            elif command.type == "downlink_file":
                self.file_service.downlink_file(
                    kubos_sat=self, gateway=gateway, command=command)
            elif command.type == "update_kubos_config_toml":
                self.file_service.update_kubos_config_toml(
                    kubos_sat=self, gateway=gateway, command=command)
            elif command.type == "update_file_list":
                self.shell_service.update_file_list(
                    kubos_sat=self, gateway=gateway, command=command)
            elif command.type == "retrieve_apps":
                self.app_service.build_from_app_service(
                    kubos_sat=self, gateway=gateway, command=command)
            elif command.type in self.app_service.apps:
                self.app_service.start_app(
                    kubos_sat=self, gateway=gateway, command=command)
            elif command.type == "uninstall_app":
                self.app_service.uninstall_app(
                    kubos_sat=self, gateway=gateway, command=command)
            elif command.type == "register_app":
                self.app_service.register_app(
                    kubos_sat=self, gateway=gateway, command=command)
            elif command.type == "kill_app":
                self.app_service.kill_app(
                    kubos_sat=self, gateway=gateway, command=command)
            else:
                raise CommandError(
                    command=command, message=f'Command Type: {command.type} is defined but does not have a resolver implemented. Please check that the definition matches a resolver case in the "command_callback" function.')

        except Exception as e:
            asyncio.ensure_future(gateway.fail_command(
                command_id=command.id, errors=[
                    f"Error Message: {e}\nError Type: {type(e)}\n\n{traceback.format_exc()}"]))

    def build_command_definitions_command(self, gateway, command):
        self.definitions = {
            "command_definitions_update": {
                "display_name": "Command Definitions Update",
                "description": "Retrieves the service information from the local config.toml and builds command definitions for each of the services within it.",
                "fields": []
            }
        }
        self.build_command_definitions()
        asyncio.ensure_future(gateway.update_command_definitions(
            system=self.name,
            definitions=self.definitions))
        asyncio.ensure_future(gateway.complete_command(
            command_id=command.id,
            output=f"Updated Definitions from config file: {self.sat_config_path}"))

    def build_command_definitions(self):
        """Builds Command Definitions"""
        self.config = toml.load(self.sat_config_path)
        for service in self.config:
            # Non GraphQL Services and raw GraphQL Commands
            if service == "file-transfer-service":
                self.file_service = FileService(
                    port=self.config["file-transfer-service"]["addr"]["port"],
                    file_client_path=self.file_client_path,
                    downlink_ip=self.config["file-transfer-service"]["downlink_ip"],
                    downlink_port=self.config["file-transfer-service"]["downlink_port"])
                self.file_service.build(kubos_sat=self)
            elif service == "shell-service":
                self.shell_service = ShellService(
                    port=self.config["shell-service"]["addr"]["port"],
                    shell_client_path=self.shell_client_path)
                self.shell_service.build(kubos_sat=self)
            else:
                graphql.build(kubos_sat=self, service=service)

            # Predefined GraphQL Service Commands
            if service == "app-service":
                self.app_service = AppService(port=self.config["app-service"]["addr"]["port"])
                self.app_service.build(kubos_sat=self)
