import subprocess
import logging

logger = logging.getLogger(__name__)


def check_client(client_path, service_name):
    if client_path is None:
        logger.warn(
            f"No {service_name} client binary defined. Skipping command definitions that require the client to resolve.")
        return False
    try:
        output = subprocess.run([client_path, "--help"],
                                capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(
            f"{service_name} client binary experienced an error, please verify it's built and in the location specified in the local gateway config. Error: {type(e)} {e.args}")
        return False
    return True
