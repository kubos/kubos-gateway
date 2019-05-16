import asyncio
import logging
import traceback
import time
import toml
import json

from kubos_gateway.spacepacket import Spacepacket

logger = logging.getLogger(__name__)


class SatProtocol:
    def __init__(self, loop, satellite):
        logger.info("SatProtocol Created")
        self.loop = loop
        self.satellite = satellite
        self.transport = None
        self.on_con_lost = loop.create_future()

    def connection_made(self, transport):
        logger.info("SatProtocol Connection Made")
        self.transport = transport

    def datagram_received(self, data, addr):
        logger.info("message received from {}: {}".format(addr,data))
        asyncio.ensure_future(self.satellite.message_received(packet=data))

    def error_received(self, exc):
        logger.error('Error received: {}'.format(exc))

    def connection_lost(self, exc):
        logger.info("Connection closed")
        self.on_con_lost.set_result(True)

class Satellite:
    def __init__(self, system_name, major_tom, sat_config_filepath, send_port, receive_port, host, bind = '127.0.0.1'):
        self.system_name = system_name
        self.major_tom = major_tom
        self.bind = bind
        self.receive_port = receive_port
        self.host = host
        self.send_port = send_port
        self.transport = None
        self.protocol = None
        self.sat_config = toml.load(sat_config_filepath)
        self.connected = False

    async def connect(self):
        logger.info(f'Connecting to the Satellite')
        loop = asyncio.get_event_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: SatProtocol(loop,self),
            local_addr=(self.bind, self.receive_port))
        self.connected = True
        logger.info(f'Connected to the Satellite')

    async def message_received(self, packet):
        sp = Spacepacket()
        sp.parse(packet)
        if sp.type == 1:
            if sp.command_id == 0:
                await self.send_metrics(sp.payload)
            else:
                logger.info(f'GraphQL Response received for command ID: {sp.command_id}')
                await self.major_tom.complete_command(command_id=sp.command_id,
                                                      output=sp.payload)
        elif sp.type == 0:
            logger.warning("UDP type is not currently supported.")

        # TODO: graphql validation
        # # {'errs': '', 'msg': { errs: '..' }}
        # if isinstance(message, dict) \
        #         and 'errs' in message \
        #         and len(message['errs']) > 0:
        #     await self.satellite.send_ack_to_mt(
        #         self.last_command_id,
        #         return_code=1,
        #         errors=[error["message"] for error in message['errs']])
        #
        # # [{'message': 'Unknown field "ping" on type "Query"',
        # #   'locations': [{'line': 1, 'column': 2}]}]
        # elif isinstance(message, list) \
        #         and len(message) > 0 \
        #         and isinstance(message[0], dict) \
        #         and 'locations' in message[0]:
        #     await self.satellite.send_ack_to_mt(
        #         self.last_command_id,
        #         return_code=1,
        #         errors=[json.dumps(error) for error in message])

    async def send_cmd(self, command_obj):
        try:
            sp = self.build_command_packet(command_obj=command_obj)
            self.send_packet(sp=sp)
            await self.major_tom.transmitted_command(command_id=command_obj.id,payload=("Hex Packet: "+sp.packet.hex()))
        except Exception as e:
            await self.major_tom.fail_command(command_obj.id, errors=["Failed to send","Error: {}".format(traceback.format_exc())])
            raise e

    async def send_packet(self, sp):
        logger.debug(f"Sending: {sp.packet} to {self.host} : {self.send_port}")
        try:
            self.transport.sendto(sp.packet, addr=(self.host,self.send_port))
        except Exception as e:
            raise e

    async def get_telemetry(self,refresh_frequency = 5):
        if "telemetry-service" not in self.sat_config:
            logger.warning('"telemetry-service" not available in satellite config.toml.')
            return
            
        # Wait for connection to establish
        while self.connected == False:
            await asyncio.sleep(1)
        logger.info('Starting Automatic Telemetry Collection')
        while True:
            try:
                sp = Spacepacket()
                now_in_utc = time.time()
                query = '{"query": "{telemetry(timestampGe:%d) {timestamp, subsystem, parameter, value }}"}' % (now_in_utc - refresh_frequency)
                sp.build(type="graphql",command_id=0,port=self.sat_config["telemetry-service"]["addr"]["port"],payload=query)
                await self.send_packet(sp=sp)
            except Exception as e:
                logger.error(f'Telemetry retrieval failed: {e}, {type(e)}, {e.args}')

            await asyncio.sleep(refresh_frequency)

    async def send_metrics(self, payload):
        payload = json.loads(payload)
        # logger.debug(f'Metrics to parse: {type(payload)}, {payload}')
        metrics = payload['data']['telemetry']
        for metric in metrics:
            ## TODO make onboard time match Major Tom
            metric['timestamp'] = metric['timestamp']*1000
            metric['system'] = self.system_name
            ## TODO make onboard key match Major Tom (parameter == metric)
            metric['metric'] = metric['parameter']
        await self.major_tom.transmit_metrics(metrics = metrics)

    def build_command_packet(self,command_obj):
        sp = Spacepacket()
        logger.info(f"received command: {command_obj.type}")
        if command_obj.type == 'kubos_graphql':
            if command_obj.fields['type'] == 'query':
                payload = "{\"query\": \"%s\"}" % command_obj.fields['request']
            elif command_obj.fields['type'] == 'mutation':
                payload = "{\"query\": \"mutation %s\"}" % command_obj.fields['request']
            else:
                asyncio.ensure_future(self.major_tom.fail_command(command_id=command_obj.id,errors=[f"Invalid Type: {command_obj.fields['type']}"]))

            sp.build(
                type = 'graphql',
                command_id = command_obj.id,
                port = command_obj.fields['service'],
                payload = payload)
            return sp
        else:
            logger.error('Command Building Failed.')
            asyncio.ensure_future(self.major_tom.fail_command(command_id=command_obj.id,errors=[f"Invalid Command: {command_obj.type}"]))
            return False
