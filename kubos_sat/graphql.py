import json
import logging
import asyncio
import requests
from kubos_sat.exceptions import *

logger = logging.getLogger(__name__)


def build(kubos_sat, service):
    graphql_command_name = "graphql-"+service
    kubos_sat.definitions[graphql_command_name] = {
        "display_name": service,
        "description": f"GraphQL Request to the {service}",
        "tags": ["Raw GraphQL"],
        "fields": [
            {"name": "ip", "type": "string",
                "value": kubos_sat.ip},
            {"name": "port", "type": "string",
                "value": kubos_sat.config[service]["addr"]["port"]},
            {"name": "query", "type": "text", "default": "{ping}"},
            {"name": "variables", "type": "text"}
        ]
    }
    kubos_sat.graphql_service_commands.append(graphql_command_name)


def graphql_command(gateway, command):
    query_with_command_updates(
        query=command.fields['query'],
        ip=command.fields['ip'],
        port=command.fields['port'],
        command_id=command.id,
        gateway=gateway,
        variables=command.fields["variables"])


def query_with_command_updates(query, ip, port, gateway, command_id, variables=None):
    """GraphQL Request Command"""
    json_result = query_with_validation(query=query, ip=ip, port=port, variables=variables)

    asyncio.ensure_future(gateway.complete_command(
        command_id=command_id,
        output=json.dumps(json_result)))


def query_with_validation(query, ip, port, variables=None):
    """GraphQL Request Command"""
    json_result = raw_query(query=query, ip=ip, port=port, variables=variables)

    if 'errors' in json_result:
        raise GraphqlError(errors=result["errors"])

    for mutation_return in json_result["data"]:
        if "success" in json_result["data"][mutation_return]:
            if not json_result["data"][mutation_return]["success"]:
                raise GraphqlMutationError(errors=json_result['data'][mutation_return]['errors'])

    return json_result


def raw_query(query, ip, port, variables=None):
    """GraphQL Query"""
    graphql = {
        'query': query,
        'variables': variables
    }
    logger.debug(json.dumps(graphql))
    url = f"http://{ip}:{port}/graphql"
    request = requests.post(
        url,
        json=graphql)

    json_result = request.json()
    logger.debug(json.dumps(json_result, indent=2))
    return json_result
