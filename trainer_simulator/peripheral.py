"""Independent Bumble GATT servers and measurement schedules."""

import asyncio
import logging
from collections import deque

from bumble import att, gatt, hci
from bumble.core import AdvertisingData, UUID
from bumble.device import Device

from .measurements import (
    FEATURES,
    SUPPORTED_POWER,
    SUPPORTED_RESISTANCE,
    TrainerLoad,
    heart_rate,
    next_deadline,
)

LOG = logging.getLogger(__name__)
WINDOW = 5.0
ROLES = {
    "trainer": ("Sim Trainer", "F0:F1:F2:F3:00:01", 0x1826, 85, 2, 0, 150),
    "hrm": ("Sim HRM", "F0:F1:F2:F3:00:02", 0x180D, 140, 1, 30, 240),
}


class Peripheral:
    def __init__(self, role, transport):
        self.role = role
        self.transport = transport
        self.name, address, service_id, self.reading, self.rate, self.minimum, self.maximum = ROLES[role]
        self.device = Device.with_hci(
            self.name, hci.Address(address), transport.source, transport.sink
        )
        self.enabled = False
        self.connection = None
        self.subscriber = None
        self.load = TrainerLoad()
        self.watts = None
        self.sent_count = 0
        self.recent_sends = deque()
        self.sending_since = None
        self.lock = asyncio.Lock()
        self.rate_changed = asyncio.Event()
        self.sender = None
        self.control_task = None
        self.background = set()
        self.error = None

        service = UUID.from_16_bits(service_id)
        self.advertising_data = bytes(AdvertisingData([
            (AdvertisingData.FLAGS, b"\x06"),
            (AdvertisingData.COMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS, bytes(service)),
            (AdvertisingData.COMPLETE_LOCAL_NAME, self.name.encode()),
        ]))
        self.measurement = gatt.Characteristic(
            UUID.from_16_bits(0x2AD2 if role == "trainer" else 0x2A37),
            gatt.Characteristic.Properties.NOTIFY,
            0,
        )
        characteristics = [self.measurement]
        if role == "trainer":
            for short, value in (
                (0x2ACC, FEATURES), (0x2AD6, SUPPORTED_RESISTANCE), (0x2AD8, SUPPORTED_POWER)
            ):
                characteristics.append(gatt.Characteristic(
                    UUID.from_16_bits(short), gatt.Characteristic.Properties.READ,
                    att.Attribute.READABLE, value,
                ))
            self.control = gatt.Characteristic(
                UUID.from_16_bits(0x2AD9),
                gatt.Characteristic.Properties.WRITE | gatt.Characteristic.Properties.INDICATE,
                att.Attribute.WRITEABLE,
                gatt.CharacteristicValue(write=self._write_control),
            )
            characteristics.append(self.control)
        self.device.add_service(gatt.Service(service, characteristics))
        self.device.on("connection", self._connected)
        self.measurement.on("subscription", self._subscription)

    @property
    def transport_lost(self):
        return self.transport.source.terminated.done()

    def _task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.background.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task):
        self.background.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            self.error = str(error) or type(error).__name__
            LOG.error("%s: %s", self.name, self.error, exc_info=error)

    async def _advertise(self):
        if self.enabled and self.connection is None:
            await self.device.start_advertising(advertising_data=self.advertising_data)
            LOG.info("%s advertising", self.name)

    async def set_power(self, enabled: bool):
        async with self.lock:
            self.error = None
            if enabled:
                if not self.enabled and self.connection is not None:
                    await self.connection.disconnect()
                if not self.enabled or (self.connection is None and not self.device.is_advertising):
                    self.enabled = True
                    try:
                        await self._advertise()
                    except Exception:
                        self.enabled = False
                        raise
            else:
                self.enabled = False
                self._stop_sending()
                self._reset_load()
                try:
                    await self.device.stop_advertising()
                finally:
                    if self.connection is not None:
                        await self.connection.disconnect()
                LOG.info("%s off", self.name)

    async def on_transport_lost(self):
        async with self.lock:
            self.enabled = False
            self.connection = None
            self._stop_sending()
            self._reset_load()
            self.error = "Bluetooth transport lost. Restart the simulator after restoring the connection."
            LOG.error("%s: %s", self.name, self.error)

    def _connected(self, connection):
        if not self.enabled or self.connection is not None:
            self._task(connection.disconnect())
            return
        self.connection = connection
        connection.on("disconnection", lambda reason: self._disconnected(connection, reason))
        LOG.info("%s connected", self.name)

    def _disconnected(self, connection, reason):
        if self.connection is connection:
            self.connection = None
            self._stop_sending()
            self._reset_load()
            LOG.info("%s disconnected (0x%02x)", self.name, reason)
            if self.enabled:
                self._task(self._restart_advertising())

    async def _restart_advertising(self):
        async with self.lock:
            if not self.device.is_advertising:
                await self._advertise()

    def _reset_load(self):
        if self.control_task is not None:
            self.control_task.cancel()
            self.control_task = None
        self.load = TrainerLoad()

    def _subscription(self, bearer, notify, _indicate):
        if bearer is not self.connection or not self.enabled:
            return
        if notify and (self.sender is None or self.sender.done()):
            self.subscriber = bearer
            self.sending_since = asyncio.get_running_loop().time()
            self.sender = self._task(self._send_measurements(bearer))
            LOG.info("%s measurements subscribed", self.name)
        elif not notify:
            self._stop_sending()
            LOG.info("%s measurements unsubscribed", self.name)

    def _stop_sending(self):
        self.subscriber = None
        if self.sender is not None:
            self.sender.cancel()
            self.sender = None
        self.recent_sends.clear()
        self.sending_since = None
        self.watts = None

    def set_rate(self, rate: float):
        if rate != self.rate:
            self.rate = rate
            self.rate_changed.set()

    async def _send_measurements(self, bearer):
        loop = asyncio.get_running_loop()
        deadline = loop.time()
        previous = None
        while self.enabled and bearer is self.subscriber:
            now = loop.time()
            if now < deadline:
                self.rate_changed.clear()
                try:
                    await asyncio.wait_for(self.rate_changed.wait(), deadline - now)
                except TimeoutError:
                    pass
                else:
                    if previous is not None:
                        deadline = max(loop.time(), previous + 1 / self.rate)
                    continue
            now = loop.time()
            if now - deadline < 1 / self.rate:
                if self.role == "trainer":
                    packet, watts = self.load.measurement(self.reading)
                else:
                    packet, watts = heart_rate(self.reading), None
                await self.device.notify_subscriber(bearer, self.measurement, packet)
                self.watts = watts
                self.sent_count += 1
                self.recent_sends.append(loop.time())
                self._trim_sends(loop.time())
            previous = deadline
            deadline = next_deadline(previous, loop.time(), self.rate)

    def _write_control(self, connection, packet):
        if not packet:
            raise att.ATT_Error(att.ATT_INVALID_ATTRIBUTE_LENGTH_ERROR)
        cccd = self.device.gatt_server.read_cccd(connection, self.control)
        if not cccd[0] & 2:
            raise att.ATT_Error(0xFD)  # Client Characteristic Configuration Improperly Configured
        if not self.enabled or connection is not self.connection or (
            self.control_task is not None and not self.control_task.done()
        ):
            raise att.ATT_Error(0xFE)  # Procedure Already In Progress
        # Let the ATT handler send its Write Response before dispatching the FTMS result.
        self.control_task = self._task(self._indicate_control(connection, packet))

    async def _indicate_control(self, connection, packet):
        response = self.load.command(packet)
        await self.device.indicate_subscriber(connection, self.control, response)
        LOG.info("FTMS opcode=0x%02x result=0x%02x target_watts=%s target_resistance=%s",
                 response[1], response[2], self.load.target_watts, self.load.target_resistance)

    def _trim_sends(self, now):
        while self.recent_sends and self.recent_sends[0] <= now - WINDOW:
            self.recent_sends.popleft()

    def snapshot(self):
        sending = self.sender is not None and not self.sender.done()
        if not self.enabled:
            status = "Off"
        elif sending:
            status = "Sending"
        elif self.connection is not None:
            status = "Connected"
        else:
            status = "Advertising"
        now = asyncio.get_running_loop().time()
        self._trim_sends(now)
        measured_rate = 0
        if sending and self.sending_since is not None:
            duration = min(WINDOW, max(now - self.sending_since, 1 / self.rate))
            measured_rate = round(len(self.recent_sends) / duration, 2)
        return {
            "enabled": self.enabled, "status": status, "reading": self.reading,
            "rate": self.rate, "actual_rate": measured_rate, "sent_count": self.sent_count,
            "watts": self.watts, "target_watts": self.load.target_watts,
            "target_resistance": self.load.target_resistance, "error": self.error,
        }
