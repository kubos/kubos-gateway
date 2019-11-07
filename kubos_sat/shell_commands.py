import asyncio
import time
import logging
import subprocess
import datetime
from kubos_sat import tools

logger = logging.getLogger(__name__)


def build(kubos_sat, service):
    success = tools.check_client(client_path=kubos_sat.shell_client_path,
                                 service_name="Shell Service")
    if not success:
        return
    if kubos_sat.file_list_directories is None:
        logger.warn(
            "File List Directories are undefined. Skipping command definitions that require file list directories to resolve.")
        return

    # Allows "all directories" as an option
    file_list_directories = kubos_sat.file_list_directories.copy()
    file_list_directories.append("all directories")
    kubos_sat.definitions["update_file_list"] = {
        "display_name": "Update File List",
        "description": "Update the list of files in common KubOS downlink Directories using the KubOS Shell Service",
        "tags": ["File Transfer"],
        "fields": [
            {"name": "directory_to_update", "type": "string", "default": "all directories",
                "range": file_list_directories},
            {"name": "shell-service-ip", "type": "string",
                "value": kubos_sat.ip},
            {"name": "shell-service-port", "type": "string",
                "value": kubos_sat.config[service]["addr"]["port"]}
        ]
    }


def update_file_list(kubos_sat, gateway, command):
    if command.fields["directory_to_update"] == "all directories":
        directories = kubos_sat.file_list_directories
    else:
        directories = [command.fields["directory_to_update"]]

    files = []
    for directory in directories:
        output = subprocess.run([
            kubos_sat.shell_client_path,
            "run",
            "-c",
            f"ls -lp {directory}"],
            capture_output=True, check=True)

        file_output = output.stdout.decode("ascii")

        logger.debug(output.stdout.decode("ascii"))

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

            # Get size and timestamp
            files.append({
                "name": directory+filename,
                "size": int(file_info_list[4]),
                "timestamp": timestamp,
                "metadata": {"full ls line": line}
            })

    asyncio.ensure_future(gateway.update_file_list(system=kubos_sat.name, files=files))
    asyncio.ensure_future(gateway.complete_command(
        command_id=command.id,
        output=f"File list updated with {len(files)} files from directories: {directories}"))
