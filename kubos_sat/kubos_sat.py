import asyncio
import time
import traceback
import logging

logger = logging.getLogger(__name__)


class KubOSSat:
    def __init__(self, name="KubOS Sat", sat_config_path=None):
        self.name = name
        self.command_definitions = {
            "command_definitions_update": {
                "display_name": "Command Definitions Update",
                "description": "Retrieves the service information from the local config.toml and builds command definitions for each of the services within it.",
                "fields": []
            }
        }

    async def command_callback(self, command, gateway):
        try:
            if command.type in self.command_definitions:
                if command.type == "command_definitions_update":
                    self.build_command_definitions()
            else:
                asyncio.ensure_future(gateway.fail_command(
                    command_id=command.id, errors=[f"Invalid command type: {command.type}"]))

        except Exception as e:
            asyncio.ensure_future(gateway.fail_command(
                command_id=command.id, errors=[
                    "Command Failed to Execute. Unknown Error Occurred.", f"Error: {traceback.format_exc()}"]))

    def build_command_definitions():
        """Builds Command Definitions"""
        pass
