import asyncio
import time
import traceback
import logging
import toml
import subprocess
import os
import datetime
import uuid
from kubos_sat import tools

logger = logging.getLogger(__name__)


def build(kubos_sat, service):
    success = tools.check_client(client_path=kubos_sat.file_client_path,
                                 service_name="File Service")
    if not success:
        return
    kubos_sat.definitions["uplink_file"] = {
        "display_name": "Uplink File",
        "description": "Uplink a staged file to the spacecraft. Leave destination_name empty to keep the same name.",
        "tags": ["File Transfer"],
        "fields": [
            {"name": "destination_directory", "type": "string",
                "default": kubos_sat.default_uplink_dir},
            {"name": "destination_name", "type": "string"},
            {"name": "file-service-ip", "type": "string",
                "value": kubos_sat.ip},
            {"name": "file-service-port", "type": "string",
                "value": kubos_sat.config[service]["addr"]["port"]},
            {"name": "gateway_download_path", "type": "string"}
        ]
    }
    kubos_sat.definitions["downlink_file"] = {
        "display_name": "Downlink File",
        "description": "Downlink a file from the Spacecraft. The full path of the file must be in the filename.",
        "tags": ["File Transfer"],
        "fields": [
            {"name": "filename", "type": "string"},
            {"name": "file-service-ip", "type": "string",
                "value": kubos_sat.ip},
            {"name": "file-service-port", "type": "string",
                "value": kubos_sat.config[service]["addr"]["port"]}
        ]
    }


def uplink_file(kubos_sat, gateway, command):
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
            [kubos_sat.file_client_path,
             "-h", kubos_sat.config["file-transfer-service"]["downlink_ip"],
             "-P", str(kubos_sat.config["file-transfer-service"]["downlink_port"]),
             "-r", kubos_sat.ip,
             "-p", str(kubos_sat.config["file-transfer-service"]["addr"]["port"]),
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


def downlink_file(kubos_sat, gateway, command):
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
    output = subprocess.run(
        [kubos_sat.file_client_path,
         "-h", kubos_sat.config["file-transfer-service"]["downlink_ip"],
         "-P", str(kubos_sat.config["file-transfer-service"]["downlink_port"]),
         "-r", kubos_sat.ip,
         "-p", str(kubos_sat.config["file-transfer-service"]["addr"]["port"]),
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
            system=kubos_sat.name,
            timestamp=time.time()*1000,
            command_id=command.id,
            metadata=None)
        asyncio.ensure_future(gateway.complete_command(
            command_id=command.id,
            output=f'Downlinked File: {command.fields["filename"]} Uploaded to Major Tom.'))
    finally:
        os.remove(local_filename)
