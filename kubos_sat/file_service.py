import asyncio
import time
import traceback
import logging
import toml
import subprocess
import os
import datetime
import uuid
from kubos_sat.tools import check_client
from kubos_sat.exceptions import *

logger = logging.getLogger(__name__)


class FileService:
    def __init__(self, port, file_client_path, downlink_ip, downlink_port):
        self.port = str(port)
        self.file_client_path = file_client_path
        self.downlink_ip = downlink_ip
        self.downlink_port = str(downlink_port)

    def build(self, kubos_sat):
        success = check_client(client_path=kubos_sat.file_client_path,
                               service_name="file-transfer-service")
        if not success:
            return
        kubos_sat.definitions["uplink_file"] = {
            "display_name": "Uplink File",
            "description": "Uplink a staged file to the spacecraft. Leave destination_name empty to keep the same name. If the app-service is present in the config file, you can also have it automatically register the app after completing the transfer.",
            "tags": ["File Transfer"],
            "fields": [
                {"name": "destination_directory", "type": "string",
                    "default": kubos_sat.default_uplink_dir},
                {"name": "destination_name", "type": "string"},
                {"name": "gateway_download_path", "type": "string"}
            ]
        }
        kubos_sat.definitions["downlink_file"] = {
            "display_name": "Downlink File",
            "description": "Downlink a file from the spacecraft. The full path of the file must be in the filename.",
            "tags": ["File Transfer"],
            "fields": [
                {"name": "filename", "type": "string"}
            ]
        }
        if "app-service" in kubos_sat.config:
            kubos_sat.definitions["uplink_file"]["fields"].append(
                {"name": "register_as_mission_app", "type": "string", "range": ["yes", "no"], "default": "no"})
        else:
            kubos_sat.definitions["uplink_file"]["fields"].append(
                {"name": "register_as_mission_app", "type": "string", "value": "no"})
        kubos_sat.definitions["update_kubos_config_toml"] = {
            "display_name": "Update KubOS Config",
            "description": "Downlinks the config file from the KubOS sat from the default location and updates the command definitions to reflect any changes.",
            "tags": ["File Transfer"],
            "fields": [
                {"name": "config_location", "type": "string", "value": "/etc/kubos-config.toml"},
                {"name": "location_config_location", "type": "string",
                    "value": kubos_sat.sat_config_path}
            ]
        }

    def uplink_file(self, kubos_sat, gateway, command):
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
            output = self.file_client(
                connection_type="upload",
                ip=kubos_sat.ip,
                local_filepath=local_filename,
                remote_filepath=destination_path)
            if command.fields["register_as_mission_app"] == "yes":
                asyncio.ensure_future(gateway.transmit_command_update(
                    command_id=command.id,
                    state="executing_on_system",
                    dict={"status": "File transferred successfully. Registering with the mission app service."}))
                kubos_sat.app_service.register_app(
                    kubos_sat=kubos_sat, gateway=gateway,
                    command=command, app_path=destination_path)
            else:
                asyncio.ensure_future(gateway.complete_command(
                    command_id=command.id,
                    output=output.stdout.decode('ascii')))
        finally:
            logger.debug(f"Deleting local file: {local_filename}")
            os.remove(local_filename)

    def downlink_file(self, kubos_sat, gateway, command):
        local_filename = f"tempfile{str(uuid.uuid4())}.tmp"
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

        output = self.file_client(
            connection_type="download",
            ip=kubos_sat.ip,
            remote_filepath=command.fields["filename"],
            local_filepath=local_filename)

        try:
            asyncio.ensure_future(gateway.transmit_command_update(
                command_id=command.id,
                state="processing_on_gateway",
                dict={
                    "status": f"File: {command.fields['filename']} successfully Downlinked! Uploading to Major Tom."}))
            gateway.upload_downlinked_file(
                filename=command.fields["filename"],
                filepath=local_filename,
                system=kubos_sat.name,
                timestamp=time.time()*1000,
                command_id=command.id,
                metadata=None)
            asyncio.ensure_future(gateway.complete_command(
                command_id=command.id,
                output=f'Downlinked File: {command.fields["filename"]} Uploaded to Major Tom.'))
        finally:
            os.remove(local_filename)

    def update_kubos_config_toml(self, kubos_sat, gateway, command):
        local_filename = f"tempfile{str(uuid.uuid4())}.tmp"

        asyncio.ensure_future(gateway.transmit_command_update(
            command_id=command.id,
            state="downlinking_from_system",
            dict={
                "status": f"Downlinking file: {command.fields['config_location']}"}))

        output = self.file_client(
            connection_type="download",
            ip=kubos_sat.ip,
            remote_filepath=command.fields["config_location"],
            local_filepath=local_filename)

        asyncio.ensure_future(gateway.transmit_command_update(
            command_id=command.id,
            state="processing_on_gateway",
            dict={
                "status": f"Config file successfully Downlinked! Rebuilding command definitions"}))

        os.remove(kubos_sat.sat_config_path)
        os.rename(local_filename, kubos_sat.sat_config_path)
        kubos_sat.build_command_definitions()
        asyncio.ensure_future(gateway.update_command_definitions(
            system=kubos_sat.name,
            definitions=kubos_sat.definitions))
        asyncio.ensure_future(gateway.complete_command(
            command_id=command.id,
            output="Command definitions updated with new config."))

    def file_client(self, connection_type, ip: str, local_filepath: str, remote_filepath: str):
        if connection_type == "upload":
            send = local_filepath
            receive = remote_filepath
        elif connection_type == "download":
            send = remote_filepath
            receive = local_filepath
        else:
            raise ValueError(
                f'connection_type must be "upload" or "download", not: {connection_type}')

        output = subprocess.run(
            [self.file_client_path,
             "-h", self.downlink_ip,
             "-P", self.downlink_port,
             "-r", ip,
             "-p", self.port,
             connection_type,
             send,
             receive],
            capture_output=True)

        logger.debug(f"Command: {output.args}")
        logger.debug(f"File Client Output: \n{output.stdout.decode('ascii')}")

        # Checking stderr is a hack until the client properly implements return codes
        if output.returncode != 0 or output.stderr != b'':
            raise FileTransferError(output=output)
        return output
