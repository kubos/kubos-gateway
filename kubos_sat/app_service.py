import logging
import json
import asyncio
import textwrap
from kubos_sat import graphql

logger = logging.getLogger(__name__)


class AppService:
    def __init__(self, port):
        self.port = port
        self.apps = []

    def build(self, kubos_sat):
        kubos_sat.definitions.update({
            "retrieve_apps": {
                "display_name": "Retrieve Apps",
                "description": "Queries the Application Service for the apps it has registered and creates commands to execute them.",
                "tags": ["Mission Apps"],
                "fields": []
            },
            "register_app": {
                "display_name": "Register App",
                "description": "Registers an application with the mission app service that is already locally accessible by the app service.",
                "tags": ["Mission Apps"],
                "fields": [
                    {"name": "app_path", "type": "string"},
                ]
            }
        })

    def build_from_app_service(self, kubos_sat, gateway, command=None):
        # remove current app commands
        for app in self.apps:
            kubos_sat.definitions.pop(app)
        self.apps = []

        query = textwrap.dedent("""
            {registeredApps {
                active
                app {name, executable, config, version, author}}}""")
        result = graphql.query_with_validation(query=query,
                                               ip=kubos_sat.ip,
                                               port=self.port)

        apps = []
        for entry in result["data"]["registeredApps"]:
            if entry["active"]:
                apps.append(entry["app"])

        if apps == []:
            logger.warning("No Active Apps")
            if command:
                asyncio.ensure_future(gateway.complete_command(
                    command_id=command.id,
                    output="No Active Apps registered"))
            return

        app_names = []
        for app in apps:
            app_names.append(app["name"])
            self.apps.append(app["name"])
            kubos_sat.definitions.update(
                {app["name"]: {
                    "display_name": f"Execute {app['name']}",
                    "description": f'Issues the "StartApp" mutation to the app service with the argument string provided. Author: {app["author"]}, Version: {app["version"]}, Config: {app["config"]}',
                    "tags": ["Mission Apps"],
                    "fields": [
                        {"name": "args", "type": "string"}
                    ]
                }}
            )
        kubos_sat.definitions.update(
            {"uninstall_app": {
                "display_name": "Uninstall App",
                "description": 'Uninstalls all versions of an app. Issue a raw mutation to uninstall only a specific version. App will still appear in command options until the "Retrieve Apps" command is re-issued.',
                "tags": ["Mission Apps"],
                "fields": [
                    {"name": "app", "type": "string", "range": app_names},
                    {"name": "version", "type": "string", "value": "all"}
                ]
            }}
        )

        kubos_sat.definitions.update(
            {"kill_app": {
                "display_name": f"Kill App",
                "description": 'Kills a running app with the given signal. The default value is 15, which is the equivalent of issuing the "kill" command in Linux.',
                "tags": ["Mission Apps"],
                "fields": [
                    {"name": "app", "type": "string", "range": app_names},
                    {"name": "signal", "type": "integer", "default": 15}
                ]
            }}
        )

        asyncio.ensure_future(gateway.update_command_definitions(
            system=kubos_sat.name,
            definitions=kubos_sat.definitions))
        if command:
            asyncio.ensure_future(gateway.complete_command(
                command_id=command.id,
                output=f"Added execution commands for registered apps: {app_names}"))

    def start_app(self, kubos_sat, gateway, command):
        args = json.dumps(command.fields["args"].split(" "))
        mutation = textwrap.dedent("""
            mutation StartApp($app_name: String!,$app_args: [String!]){
                startApp(name: $app_name, args: $app_args) {
                    success,errors,pid
                }}""")
        variables = {
            "app_name": command.type,
            "app_args": args
        }
        graphql.query_with_command_updates(query=mutation,
                                           ip=kubos_sat.ip,
                                           port=self.port,
                                           gateway=gateway,
                                           command_id=command.id,
                                           variables=variables)

    def uninstall_app(self, kubos_sat, gateway, command):
        mutation = textwrap.dedent("""
            mutation Uninstall($app_name: String!){
                uninstall(name:$app_name){
                    success,errors
                }}""")
        variables = {
            "app_name": command.fields["app"]
        }
        graphql.query_with_command_updates(query=mutation,
                                           ip=kubos_sat.ip,
                                           port=self.port,
                                           gateway=gateway,
                                           command_id=command.id,
                                           variables=variables)

    def kill_app(self, kubos_sat, gateway, command):
        mutation = textwrap.dedent("""
            mutation KillApp($app_name: String!,$signal: Int){
                killApp(name: $app_name, signal: $signal) {
                    success,errors
                }}""")
        variables = {
            "app_name": command.fields["app"],
            "signal": int(command.fields["signal"])
        }
        graphql.query_with_command_updates(query=mutation,
                                           ip=kubos_sat.ip,
                                           port=self.port,
                                           gateway=gateway,
                                           command_id=command.id,
                                           variables=variables)

    def register_app(self, kubos_sat, gateway, command, app_path=None):
        # Allows register to be called from other commands as well
        if not app_path:
            app_path = command.fields["app_path"]
        mutation = textwrap.dedent("""
            mutation Register($app_path: String!){
                register(path: $app_path) {
                    success, errors,
                    entry { app {
                        name, executable, config
                    }}
                }}""")
        variables = {
            "app_path": app_path
        }
        graphql.query_with_command_updates(query=mutation,
                                           ip=kubos_sat.ip,
                                           port=self.port,
                                           gateway=gateway,
                                           command_id=command.id,
                                           variables=variables)
