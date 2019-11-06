import asyncio
import time
import traceback
import logging
import toml
import subprocess
import os
import datetime
import uuid

logger = logging.getLogger(__name__)


class FileCommands:
    def __init__(self, KubosSat):
        self.kubos_sat = KubosSat

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
                [self.kubos_sat.file_client_path,
                 "-h", self.kubos_sat.config["file-transfer-service"]["downlink_ip"],
                 "-P", str(self.kubos_sat.config["file-transfer-service"]["downlink_port"]),
                 "-r", self.kubos_sat.ip,
                 "-p", str(self.kubos_sat.config["file-transfer-service"]["addr"]["port"]),
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
            [self.kubos_sat.file_client_path,
             "-h", self.kubos_sat.config["file-transfer-service"]["downlink_ip"],
             "-P", str(self.kubos_sat.config["file-transfer-service"]["downlink_port"]),
             "-r", self.kubos_sat.ip,
             "-p", str(self.kubos_sat.config["file-transfer-service"]["addr"]["port"]),
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
                system=self.kubos_sat.name,
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
            directories = self.kubos_sat.file_list_directories
        else:
            directories = [command.fields["directory_to_update"]]

        files = []
        for directory in directories:
            output = subprocess.run([
                self.kubos_sat.shell_client_path,
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

        asyncio.ensure_future(gateway.update_file_list(system=self.kubos_sat.name, files=files))
        asyncio.ensure_future(gateway.complete_command(
            command_id=command.id,
            output=f"File list updated with {len(files)} files from directories: {directories}"))
