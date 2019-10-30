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
import tempfile

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

    async def cancel_callback(self, command_id, gateway):
        asyncio.ensure_future(gateway.cancel_command(command_id=command_id))

    async def command_callback(self, command, gateway):
        try:
            if command.type in self.definitions:
                if command.type == "command_definitions_update":
                    self.build_command_definitions()
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
                    self.uplink_file(gateway=gateway, command=command)
                elif command.type == "downlink_file":
                    self.downlink_file(gateway=gateway, command=command)
                elif command.type == "shell-command":
                    asyncio.ensure_future(gateway.fail_command(
                        command_id=command.id,
                        errors=[f"Command not yet implemented"]))
                elif command.type == "update_file_list":
                    self.update_file_list(gateway=gateway, command=command)
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
                if self.file_client_path is None:
                    logger.warn(
                        "No file transfer client binary defined. Skipping command definitions that require the file client to resolve.")
                    continue
                try:
                    output = subprocess.run([self.file_client_path, "--help"],
                                            capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    logger.error(
                        f"Error reading file client binary: {type(e)} {e.args}  \nPlease verify it's built and in the location specified in the local gateway config.")
                    continue

                self.definitions["uplink_file"] = {
                    "display_name": "Uplink File",
                    "description": "Uplink a staged file to the spacecraft. Leave destination_name empty to keep the same name.",
                    "tags": ["File Transfer"],
                    "fields": [
                        {"name": "destination_directory", "type": "string", "default": "/home/kubos/"},
                        {"name": "destination_name", "type": "string"},
                        {"name": "file-service-ip", "type": "string",
                            "value": self.ip},
                        {"name": "file-service-port", "type": "string",
                            "value": self.config[service]["addr"]["port"]},
                        {"name": "gateway_download_path", "type": "string"}
                    ]
                }
                self.definitions["downlink_file"] = {
                    "display_name": "Downlink File",
                    "description": "Downlink a file from the Spacecraft. The full path of the file must be in the filename.",
                    "tags": ["File Transfer"],
                    "fields": [
                        {"name": "filename", "type": "string"},
                        {"name": "file-service-ip", "type": "string",
                            "value": self.ip},
                        {"name": "file-service-port", "type": "string",
                            "value": self.config[service]["addr"]["port"]}
                    ]
                }
            elif service == "shell-service":
                if self.shell_client_path is None:
                    logger.warn(
                        "No shell service client binary defined. Skipping command definitions that require the shell client to resolve.")
                    continue
                try:
                    output = subprocess.run([self.shell_client_path, "--help"],
                                            capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    logger.error(
                        f"Shell Service client binary experienced an error, please verify it's built and in the location specified in the local gateway config. Error: {type(e)} {e.args}")
                    continue
                if self.file_list_directories is None:
                    logger.warn(
                        "File List Directories are undefined. Skipping command definitions that require file list directories to resolve.")
                    continue

                # Allows "all directories" as an option
                file_list_directories = self.file_list_directories.copy()
                file_list_directories.append("all directories")
                self.definitions["update_file_list"] = {
                    "display_name": "Update File List",
                    "description": "Update the list of files in common KubOS downlink Directories using the KubOS Shell Service",
                    "tags": ["File Transfer"],
                    "fields": [
                        {"name": "directory_to_update", "type": "string", "default": "all directories",
                            "range": file_list_directories},
                        {"name": "shell-service-ip", "type": "string",
                            "value": self.ip},
                        {"name": "shell-service-port", "type": "string",
                            "value": self.config[service]["addr"]["port"]}
                    ]
                }
            else:
                self.definitions[service] = {
                    "display_name": service,
                    "description": f"GraphQL Request to the {service}",
                    "tags": ["Raw GraphQL"],
                    "fields": [
                        {"name": "ip", "type": "string",
                            "value": self.ip},
                        {"name": "port", "type": "string",
                            "value": self.config[service]["addr"]["port"]},
                        {"name": "graphql", "type": "text", "default": "{ping}"}
                    ]
                }

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

    def uplink_file(self, gateway, command):
        logger.debug("Downloading file from Major Tom")
        asyncio.ensure_future(gateway.transmit_command_update(
            command_id=command.id,
            state="processing_on_gateway",
            dict={
                "status": "Downloading Staged File from Major Tom for Transmission"}))
        local_filename, content = gateway.download_staged_file(
            gateway_download_path=command.fields["gateway_download_path"])
        logger.debug(f'Writing file: "{local_filename}" locally')
        asyncio.ensure_future(gateway.transmit_command_update(
            command_id=command.id,
            state="processing_on_gateway",
            dict={
                "status": f"Writing file: {local_filename} locally"}))
        with open(local_filename, "wb") as f:
            f.write(content)
        try:
            if command.fields["destination_name"] == "":
                destination_name = local_filename
            else:
                destination_name = command.fields["destination_name"]
            destination_path = command.fields["destination_directory"] + destination_name
            asyncio.ensure_future(gateway.transmit_command_update(
                command_id=command.id,
                state="uplinking_to_system",
                dict={
                    "status": f"Uploading {local_filename} to {destination_path} on satellite."}))
            output = subprocess.run(
                [self.file_client_path,
                 "-h", self.config["file-transfer-service"]["downlink_ip"],
                 "-P", str(self.config["file-transfer-service"]["downlink_port"]),
                 "-r", self.ip,
                 "-p", str(self.config["file-transfer-service"]["addr"]["port"]),
                 "upload",
                 local_filename,
                 destination_path],
                capture_output=True)
            # Checking stderr is a hack until the client properly implements return codes
            if output.returncode == 0 and output.stderr == b'':
                asyncio.ensure_future(gateway.complete_command(
                    command_id=command.id,
                    output=output.stdout.decode('ascii')))
            else:
                asyncio.ensure_future(gateway.fail_command(
                    command_id=command.id,
                    errors=["File Client failed to transfer the File: ", output.stderr.decode('ascii')]))
        finally:
            logger.debug(f"Deleting local file: {local_filename}")
            os.remove(local_filename)

    def downlink_file(self, gateway, command):
        local_filename = "tempfile.tmp"
        if command.fields["filename"].strip() == '':
            asyncio.ensure_future(gateway.fail_command(
                command_id=command.id,
                errors=["filename cannot be empty"]))
            return

        asyncio.ensure_future(gateway.transmit_command_update(
            command_id=command.id,
            state="downlinking_from_system",
            dict={
                "status": f"Downlinking file: {command.fields['filename']}"}))
        output = subprocess.run(
            [self.file_client_path,
             "-h", self.config["file-transfer-service"]["downlink_ip"],
             "-P", str(self.config["file-transfer-service"]["downlink_port"]),
             "-r", self.ip,
             "-p", str(self.config["file-transfer-service"]["addr"]["port"]),
             "download",
             command.fields["filename"],
             local_filename],
            capture_output=True)

        logger.debug(output.stdout.decode("ascii"))

        # os path check is a hack until the file client implements return codes properly.
        if output.returncode != 0 or not os.path.isfile(local_filename):
            asyncio.ensure_future(gateway.fail_command(
                command_id=command.id,
                errors=["File Client failed to transfer the File: ", output.stderr.decode('ascii')]))
            return
        try:
            asyncio.ensure_future(gateway.transmit_command_update(
                command_id=command.id,
                state="processing_on_gateway",
                dict={
                    "status": f"File: {command.fields['filename']} successfully Downlinked! Uploading to Major Tom."}))
            gateway.upload_downlinked_file(
                filename=command.fields["filename"],
                filepath=local_filename,
                system=self.name,
                timestamp=time.time()*1000,
                command_id=command.id,
                metadata=None)
            asyncio.ensure_future(gateway.complete_command(
                command_id=command.id,
                output=f'Downlinked File: {command.fields["filename"]} Uploaded to Major Tom.'))
        finally:
            os.remove(local_filename)

    def update_file_list(self, gateway, command):
        if command.fields["directory_to_update"] == "all directories":
            directories = self.file_list_directories
        else:
            directories = [command.fields["directory_to_update"]]

        files = []
        for directory in directories:
            output = subprocess.run([
                self.shell_client_path,
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

        asyncio.ensure_future(gateway.update_file_list(system=self.name, files=files))
        asyncio.ensure_future(gateway.complete_command(
            command_id=command.id,
            output=f"File list updated with {len(files)} files from directories: {directories}"))
