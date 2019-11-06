import asyncio
import traceback
import logging
import toml
import subprocess

logger = logging.getLogger(__name__)


class BuildCommandDefinitions:
    def __init__(self, KubosSat):
        self.kubos_sat = KubosSat

    def build(self):
        """Builds Command Definitions"""
        self.kubos_sat.config = toml.load(self.kubos_sat.sat_config_path)
        for service in self.kubos_sat.config:
            if service == "file-transfer-service":
                if self.kubos_sat.file_client_path is None:
                    logger.warn(
                        "No file transfer client binary defined. Skipping command definitions that require the file client to resolve.")
                    continue
                try:
                    output = subprocess.run([self.kubos_sat.file_client_path, "--help"],
                                            capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    logger.error(
                        f"Error reading file client binary: {type(e)} {e.args}  \nPlease verify it's built and in the location specified in the local gateway config.")
                    continue

                self.kubos_sat.definitions["uplink_file"] = {
                    "display_name": "Uplink File",
                    "description": "Uplink a staged file to the spacecraft. Leave destination_name empty to keep the same name.",
                    "tags": ["File Transfer"],
                    "fields": [
                        {"name": "destination_directory", "type": "string", "default": "/home/kubos/"},
                        {"name": "destination_name", "type": "string"},
                        {"name": "file-service-ip", "type": "string",
                            "value": self.kubos_sat.ip},
                        {"name": "file-service-port", "type": "string",
                            "value": self.kubos_sat.config[service]["addr"]["port"]},
                        {"name": "gateway_download_path", "type": "string"}
                    ]
                }
                self.kubos_sat.definitions["downlink_file"] = {
                    "display_name": "Downlink File",
                    "description": "Downlink a file from the Spacecraft. The full path of the file must be in the filename.",
                    "tags": ["File Transfer"],
                    "fields": [
                        {"name": "filename", "type": "string"},
                        {"name": "file-service-ip", "type": "string",
                            "value": self.kubos_sat.ip},
                        {"name": "file-service-port", "type": "string",
                            "value": self.kubos_sat.config[service]["addr"]["port"]}
                    ]
                }
            elif service == "shell-service":
                if self.kubos_sat.shell_client_path is None:
                    logger.warn(
                        "No shell service client binary defined. Skipping command definitions that require the shell client to resolve.")
                    continue
                try:
                    output = subprocess.run([self.kubos_sat.shell_client_path, "--help"],
                                            capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    logger.error(
                        f"Shell Service client binary experienced an error, please verify it's built and in the location specified in the local gateway config. Error: {type(e)} {e.args}")
                    continue
                if self.kubos_sat.file_list_directories is None:
                    logger.warn(
                        "File List Directories are undefined. Skipping command definitions that require file list directories to resolve.")
                    continue

                # Allows "all directories" as an option
                file_list_directories = self.kubos_sat.file_list_directories.copy()
                file_list_directories.append("all directories")
                self.kubos_sat.definitions["update_file_list"] = {
                    "display_name": "Update File List",
                    "description": "Update the list of files in common KubOS downlink Directories using the KubOS Shell Service",
                    "tags": ["File Transfer"],
                    "fields": [
                        {"name": "directory_to_update", "type": "string", "default": "all directories",
                            "range": file_list_directories},
                        {"name": "shell-service-ip", "type": "string",
                            "value": self.kubos_sat.ip},
                        {"name": "shell-service-port", "type": "string",
                            "value": self.kubos_sat.config[service]["addr"]["port"]}
                    ]
                }
            else:
                self.kubos_sat.definitions[service] = {
                    "display_name": service,
                    "description": f"GraphQL Request to the {service}",
                    "tags": ["Raw GraphQL"],
                    "fields": [
                        {"name": "ip", "type": "string",
                            "value": self.kubos_sat.ip},
                        {"name": "port", "type": "string",
                            "value": self.kubos_sat.config[service]["addr"]["port"]},
                        {"name": "graphql", "type": "text", "default": "{ping}"}
                    ]
                }
