import asyncio
import time
import traceback
import logging
import toml
import requests
import json
import subprocess
import os

logger = logging.getLogger(__name__)


class KubosSat:
    def __init__(self, name, ip, sat_config_path, file_client_path=None, shell_client_path=None):
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

    async def cancel_callback(self, command_id, gateway):
        asyncio.ensure_future(gateway.cancel_command(command_id=command_id))

    async def command_callback(self, command, gateway):
        try:
            if command.type in self.definitions:
                if command.type == "command_definitions_update":
                    self.build_command_definitions(gateway=gateway)
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
                elif command.type == "telemetry-autofetch":
                    asyncio.ensure_future(self.autorequest_telemetry(
                        gateway=gateway,
                        period_sec=command.fields["period"],
                        duration_sec=command.fields["duration"],
                        command_id=command.id))
                elif command.type == "update_file_list":
                    self.update_file_list(gate)
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

    def build_command_definitions(self, gateway):
        """Builds Command Definitions"""
        self.config = toml.load(self.sat_config_path)
        for service in self.config:
            if service == "file-transfer-service":
                if self.file_client_path is None:
                    asyncio.ensure_future(gateway.transmit_events(events=[{
                        "system": self.name,
                        "type": "File Transfer Client",
                        "level": "warning",
                        "message": "No file transfer client binary defined. Please verify it's built and in the location specified in the local gateway config."
                    }]))
                    logger.warning("No file transfer client binary defined.")
                    continue
                try:
                    output = subprocess.run([self.file_client_path, "--help"],
                                            capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    asyncio.ensure_future(gateway.transmit_events(events=[{
                        "system": self.name,
                        "type": "File Transfer Client",
                        "level": "warning",
                        "message": "File transfer client binary experienced an error, please verify it's built and in the location specified in the local gateway config."
                    }]))
                    logger.error(f"Error reading file client binary: {type(e)} {e.args}")
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
                    asyncio.ensure_future(gateway.transmit_events(events=[{
                        "system": self.name,
                        "type": "Shell Service Client",
                        "level": "warning",
                        "message": "No shell service client binary defined. Please verify it's built and in the location specified in the local gateway config."
                    }]))
                    logger.warning("No shell service client binary defined.")
                    continue
                try:
                    output = subprocess.run([self.shell_client_path, "--help"],
                                            capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    asyncio.ensure_future(gateway.transmit_events(events=[{
                        "system": self.name,
                        "type": "Shell Service Client",
                        "level": "warning",
                        "message": "Shell Service client binary experienced an error, please verify it's built and in the location specified in the local gateway config."
                    }]))
                    logger.error(f"Error reading file client binary: {type(e)} {e.args}")
                    continue
                self.definitions["update_file_list"] = {
                    "display_name": "Update File List",
                    "description": "Update the list of files in common KubOS downlink Directories using the KubOS Shell Service",
                    "tags": ["File Transfer"],
                    "fields": [
                        {"name": "directory_to_update", "type": "string", "default": "all",
                            "range": ["all", "/var/log/", "/Users/jessecoffey/Workspace/misc/"]},  # Other directories to test: "/home/kubos/", "/upgrade/"
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
            if service == "telemetry-service":
                self.definitions["telemetry-autofetch"] = {
                    "display_name": "Autofetch Telemetry",
                    "description": "Automatically requests the most recent telemetry from the Telemetry Database Service",
                    "tags": ["development"],
                    "fields": [
                        {"name": "period", "type": "integer", "default": 10},
                        {"name": "duration", "type": "integer", "default": 300}
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

    async def autorequest_telemetry(self, gateway, period_sec, duration_sec, command_id=None):
        if period_sec >= duration_sec:
            raise ValueError("Duration must be longer than the period.")

        if "telemetry-service" not in self.definitions:
            logger.error("telemetry-service is not present.")
            if command_id:
                asyncio.ensure_future(gateway.fail_command(
                    command_id=command_id,
                    errors=["telemetry-service is not present on the system"]))
            return

        start_time = time.time()
        if command_id:
            asyncio.ensure_future(gateway.complete_command(
                command_id=command_id,
                output="Telemetry Autofetch Started"))
        while True:
            # Make the Query
            graphql = """
                {telemetry (timestampGe:%d){
                  timestamp
                  subsystem
                  parameter
                  value
                }}
            """ % (time.time()-period_sec)  # TODO: Change this to milliseconds when we update the tlm service

            # Retrieve Telemetry
            try:
                result = self.query(
                    graphql=graphql,
                    ip=self.ip,
                    port=self.config['telemetry-service']['addr']['port'])
            except requests.exceptions.RequestException as e:
                asyncio.ensure_future(gateway.transmit_events(events=[{
                    "system": self.name,
                    "type": "Telemetry Autofetching",
                    "command_id": command_id,
                    "level": "error",
                    "message": f"telemetry-service is not responding. ",
                    "timestamp": time.time()*1000
                }]))
                break
            except Exception as e:
                asyncio.ensure_future(gateway.transmit_events(events=[{
                    "system": self.name,
                    "type": "Telemetry Autofetching",
                    "command_id": command_id,
                    "level": "error",
                    "message": f"telemetry-service query failed. Error: {traceback.format_exc()}",
                    "timestamp": time.time()*1000
                }]))
                break

            # Check that it completed successfully
            if 'errors' in result:
                asyncio.ensure_future(gateway.transmit_events(events=[{
                    "system": self.name,
                    "type": "Telemetry Autofetching",
                    "command_id": command_id,
                    "debug": json.dumps(result),
                    "level": "warning",
                    "message": "telemetry-service responded with an error. Stopping autofetch.",
                    "timestamp": time.time()*1000
                }]))
                break
            else:
                # We successfully talked to the service, so add a metric that reflects that.
                metrics = [{
                    "system": self.name,
                    "subsystem": "status",
                    "metric": "connected",
                    "value": 1}]

            # Check that there is telemetry present
            if result['data']['telemetry'] == []:
                asyncio.ensure_future(gateway.transmit_events(events=[{
                    "system": self.name,
                    "type": "Telemetry Autofetching",
                    "command_id": command_id,
                    "debug": json.dumps(result),
                    "level": "debug",
                    "message": "telemetry-service had no data.",
                    "timestamp": time.time()*1000
                }]))
            # Submit Telemetry
            for measurement in result['data']['telemetry']:
                metrics.append({
                    "system": self.name,
                    "subsystem": "status",
                    "metric": "connected",
                    "value": 1
                })
            asyncio.ensure_future(gateway.transmit_metrics(metrics=metrics))

            # Wait for next iteration
            await asyncio.sleep(period_sec)

            # Check if duration has elapsed
            if (time.time() - start_time) >= duration_sec:
                break

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
        if command.fields["filename"] == '':
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

        # os path check is a hack until the file client implements return codes properly.
        if output.returncode != 0 or not os.path.exists(local_filename):
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
        asyncio.ensure_future(gateway.fail_command(
            command_id=command.id,
            errors=["Update File List command is not yet implemented."]))
