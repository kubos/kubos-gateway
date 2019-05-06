import struct
import logging

logger = logging.getLogger(__name__)

class Spacepacket:
    """
    This class only implements the fields that the KubOS communication services
    uses to pass data over a radio link. The unused fields of the primary header
    are shown in the code, but not supported.
    """

    def __init__(self):
        self.packet = None
        self.type = None
        self.command_id = None
        self.port = None
        self.payload = None

    def build(self,type,command_id,port,payload):
        self.type = type
        self.command_id = command_id
        self.port = port
        self.payload = payload

        #######################################
        # PRIMARY HEADER
        version_number = 0 # Unused
        packet_type = 0 # Unused
        sec_header_flag = 0 # Unused
        if type == 'udp':
            application_process_id = 0
        elif type == 'graphql':
            application_process_id = 1
        else:
            raise ValueError("invalid packet type, valid types are: 'udp' or 'graphql'.")
        sequence_flags = 0 # Unused
        packet_sequence_count = 0 # Unused
        packet_data_length = 10 + len(payload) # secondary header (10) + payload
        if packet_data_length > 65535:
            raise ValueError("payload larger than max length")

        # Build 2 bytes at a time
        ph0 = application_process_id
        frame = ph0.to_bytes(2,byteorder='big')
        ph1 = 0 # Unused not set
        frame += ph1.to_bytes(2,byteorder='big')
        ph2 = packet_data_length
        frame += ph2.to_bytes(2,byteorder='big')

        #######################################
        # SECONDARY HEADER
        sh0 = command_id
        frame += sh0.to_bytes(8,byteorder='big')
        sh1 = port
        frame += sh1.to_bytes(2,byteorder='big')

        #######################################
        # PAYLOAD

        frame += payload.encode('utf-8')

        self.packet = frame

    def parse(self,packet: bytes):
        headers = packet[0:16]
        [self.type,_,total_length,self.command_id,self.port] = struct.unpack(">HHHqH",headers)
        self.length = total_length - 10 # subtract secondary header
        if self.type == 1:
            self.payload = packet[16:].decode('utf-8')
        elif self.type == 0:
            self.payload = packet[16:]
        else:
            logger.error('Packet Type is invalid: {}'.format(self.type))
