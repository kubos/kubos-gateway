import asyncio
import logging

from kubos_adapter.command_result import CommandResult
from kubos_adapter.major_tom import Command
from kubos_adapter.sat_service import SatService

logger = logging.getLogger(__name__)

"""
passthrough query and mutation
"""

class ApplicationService(SatService):
    def __init__(self, port):
        super().__init__('application', port)

    def match(self, command):
        return command.subsystem == "application_service"  # Matches all subsystems

