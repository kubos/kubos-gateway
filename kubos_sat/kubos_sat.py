import asyncio
import time
import traceback
import logging
import toml
import requests
import json

logger = logging.getLogger(__name__)


class KubosSat:
    def __init__(self, name, sat_config_path):
        self.name = name
        self.sat_config_path = sat_config_path
        self.config = None
        self.definitions = {
            "command_definitions_update": {
                "display_name": "Command Definitions Update",
                "description": "Retrieves the service information from the local config.toml and builds command definitions for each of the services within it.",
                "fields": []
            }
        }

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
                    asyncio.ensure_future(gateway.fail_command(
                        command_id=command.id,
                        errors=[f"Command not yet implemented"]))
                elif command.type == "downlink_file":
                    asyncio.ensure_future(gateway.fail_command(
                        command_id=command.id,
                        errors=[f"Command not yet implemented"]))
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
                self.definitions["uplink_file"] = {
                    "display_name": "Uplink File",
                    "description": "Uplink a staged file to the spacecraft.",
                    "fields": [
                        {"name": "gateway_download_path", "type": "string"}
                    ]
                }
                self.definitions["downlink_file"] = {
                    "display_name": "Downlink File",
                    "description": "Downlink an image from the Spacecraft.",
                    "fields": [
                        {"name": "filename", "type": "string"},
                        {"name": "file-service-ip", "type": "string",
                            "value": self.config[service]["addr"]["ip"]},
                        {"name": "file-service-port", "type": "string",
                            "value": self.config[service]["addr"]["port"]}
                    ]
                }
            elif service == "shell-service":
                self.definitions["shell-command"] = {
                    "display_name": "Shell Service Command",
                    "description": "Command to be executed using the shell service",
                    "fields": [
                        {"name": "ip", "type": "string",
                            "value": self.config[service]["addr"]["ip"]},
                        {"name": "port", "type": "string",
                            "value": self.config[service]["addr"]["port"]},
                        {"name": "shell-command", "type": "string"}
                    ]
                }
            else:
                self.definitions[service] = {
                    "display_name": service,
                    "description": f"GraphQL Request to the {service}",
                    "fields": [
                        {"name": "ip", "type": "string",
                            "value": self.config[service]["addr"]["ip"]},
                        {"name": "port", "type": "string",
                            "value": self.config[service]["addr"]["port"]},
                        {"name": "graphql", "type": "text", "default": "{ping}"}
                    ]
                }
            if service == "telemetry-service":
                self.definitions["telemetry-autofetch"] = {
                    "display_name": "Autofetch Telemetry",
                    "description": "Automatically requests the most recent telemetry from the Telemetry Database Service",
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
                    ip=self.config['telemetry-service']['addr']['ip'],
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
            else:
                # Submit Telemetry
                for measurement in result['data']['telemetry']:
                    pass

            # Wait for next iteration
            await asyncio.sleep(period_sec)

            # Check if duration has elapsed
            if (time.time() - start_time) >= duration_sec:
                break
