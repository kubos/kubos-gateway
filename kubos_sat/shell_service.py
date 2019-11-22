import asyncio
import time
import logging
import subprocess
import datetime
from kubos_sat.tools import check_client
from kubos_sat.exceptions import *

logger = logging.getLogger(__name__)


class ShellService:
    def __init__(self, port, shell_client_path):
        self.port = str(port)
        self.shell_client_path = shell_client_path

    def build(self, kubos_sat):
        success = check_client(client_path=self.shell_client_path,
                               service_name="shell-service")
        if not success:
            return
        if kubos_sat.file_list_directories is None:
            logger.warn(
                "File List Directories are undefined. Skipping command definitions that require file list directories to resolve.")
            return

        # Allows "all directories" as an option
        file_list_directories = kubos_sat.file_list_directories.copy()
        file_list_directories.append("All Directories")
        kubos_sat.definitions["update_file_list"] = {
            "display_name": "Update File List",
            "description": "Update the list of files in one or all downlink directories using the KubOS Shell Service",
            "tags": ["File Transfer"],
            "fields": [
                {"name": "directory_to_update", "type": "string", "default": "All Directories",
                    "range": file_list_directories}
            ]
        }

    def update_file_list(self, kubos_sat, gateway, command):
        if command.fields["directory_to_update"] == "All Directories":
            directories = kubos_sat.file_list_directories
        else:
            directories = [command.fields["directory_to_update"]]

        files = []
        for directory in directories:
            output = self.shell_client(ip=kubos_sat.ip, command=f"ls -lp {directory}")
            logger.debug(f"Command: {output.args}")
            logger.debug(f"Shell Client Output: \n{output.stdout.decode('ascii')}")

            # TODO: Check that the shell service actually responded. Currently the client gives no way to differentiate between no files being in the directory and a timeout occurring.

            file_output = output.stdout.decode("ascii")

            # Each line is a line of output from the command response
            output_list = file_output.split('\n')

            for line in output_list:
                # Split each line into sections
                line_list = line.split(" ")

                # Throw out spaces and empty fields
                file_info_list = []
                for field in line_list:
                    if field not in ["", " "]:
                        file_info_list.append(field)

                # Make sure it's a output line
                if len(file_info_list) < 9:
                    continue

                # Throw out Directories
                if file_info_list[-1][-1] == "/":
                    continue

                # Reassemble filename
                filename = ""
                for filename_part in file_info_list[8:]:
                    # Add Spaces back in (doesn't work if there were 2 spaces in the filename)
                    filename += filename_part + " "
                filename = filename[:-1]  # Remove Trailing Space

                # Commonize file timestamp string
                if len(file_info_list[7]) == 4:
                    string_time = "00:00" + file_info_list[5] + \
                        '{:0>2}'.format(file_info_list[6]) + file_info_list[7]
                else:
                    string_time = file_info_list[7] + file_info_list[5] + \
                        '{:0>2}'.format(file_info_list[6]) + str(datetime.datetime.now().year)

                # Strip time and get datetime object
                timestamp = (datetime.datetime.strptime(string_time, "%H:%M%b%d%Y") -
                             datetime.datetime.utcfromtimestamp(0)).total_seconds()*1000

                if timestamp == 0:
                    timestamp = 1  # Timestamp cannot be 0 for Major Tom

                # Append File
                files.append({
                    "name": directory+filename,
                    "size": int(file_info_list[4]),
                    "timestamp": timestamp,
                    "metadata": {"full ls line": line, "directory": directory, "filename": filename}
                })

        asyncio.ensure_future(gateway.update_file_list(system=kubos_sat.name, files=files))
        asyncio.ensure_future(gateway.complete_command(
            command_id=command.id,
            output=f"File list updated with {len(files)} files from directories: {directories}"))

    def shell_client(self, ip: str, command: str):
        return subprocess.run([
            self.shell_client_path,
            "-i", ip,
            "-p", self.port,
            "run",
            "-c", command],
            capture_output=True, check=True)
