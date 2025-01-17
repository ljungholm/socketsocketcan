import multiprocessing
from typing import Optional, Dict, Union, List

import psutil
from can.interfaces.socketcan.constants import CAN_EFF_FLAG
# noinspection PyUnresolvedReferences
from tcpclient import tcpclient


class TCPClient(object):

    def __init__(self, channel: str, hostname: str, port: int, can_filters: List[Dict[str, Union[int, bool]]] = None,
                 use_unordered_map=False, limit_recv_rate_hz: int = None):
        """
        :param channel: Can interface to use.
        :param hostname: Hostname used for the socket.
        :param port: The port to use for the TCP connection.
        :param can_filters: Can ID and mask to apply to all incoming frames.
        :param use_unordered_map: Override the any old frames if a new one is received before the server has had time
        to read it yet. This can be used together with "limit_recv_rate_hz" to limit the update rate while still
        receiving the latest data.
        :param limit_recv_rate_hz: Allow to limit the receive update rate.
        """
        self.channel = channel
        self.hostname = hostname
        self.port = port
        self.can_filters = can_filters
        self.use_unordered_map = use_unordered_map
        self.limit_recv_rate_hz = limit_recv_rate_hz

        # Run the client in a separate process, so it does not block the main thread
        self._tcp_client_process = multiprocessing.Process(target=self._tcp_client, args=(channel, hostname, port,
                                                                                          can_filters,
                                                                                          use_unordered_map,
                                                                                          limit_recv_rate_hz))
        self._tcp_client_process.daemon = True
        self._tcp_client_process.start()

    @property
    def pid(self):
        return self._tcp_client_process.pid

    def is_alive(self):
        self._tcp_client_process.is_alive()

    def join(self, timeout=None):
        self._tcp_client_process.join(timeout=timeout)

    def shutdown(self, timeout=None) -> Optional[int]:
        # Send SIGTERM to the process and wait for it to finish
        if self._tcp_client_process.is_alive():
            self._tcp_client_process.terminate()
            self._tcp_client_process.join(timeout=timeout)

        # The exitcode will be None if the process is still alive
        return self._tcp_client_process.exitcode

    def kill(self, timeout=None):
        # Get an instance of the process
        process = psutil.Process(self.pid)

        # Send SIGKILL to the process
        process.kill()

        # Wait for the process to end
        return process.wait(timeout)

    @staticmethod
    def _tcp_client(channel, hostname, port, can_filters, use_unordered_map, limit_recv_rate_hz):
        if can_filters is None:
            can_filters = [{'can_id': 0, 'can_mask': 0}]

        # See "pack_filters" in the socketcan interface
        filter_data = []
        for can_filter in can_filters:
            can_id = can_filter['can_id']
            can_mask = can_filter['can_mask']
            if 'extended' in can_filter:
                # Match on either 11-bit OR 29-bit messages instead of both
                can_mask |= CAN_EFF_FLAG
                if can_filter['extended']:
                    can_id |= CAN_EFF_FLAG
            filter_data.append({'can_id': can_id, 'can_mask': can_mask})

        tcpclient(channel, hostname, port, filter_data, use_unordered_map, limit_recv_rate_hz)
