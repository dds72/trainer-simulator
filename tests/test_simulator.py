import asyncio
import struct
import unittest
from types import SimpleNamespace

from bumble.controller import Controller
from bumble.core import UUID
from bumble.device import Device, Peer
from bumble.hci import Address
from bumble.link import LocalLink

from trainer_simulator.measurements import TrainerLoad, heart_rate, next_deadline
from trainer_simulator.peripheral import Peripheral


class MeasurementTests(unittest.TestCase):
    def test_current_byte_fixtures_and_load_model(self):
        load = TrainerLoad()
        self.assertEqual(bytes.fromhex("6400f609aa00000000"), load.measurement(85)[0])
        self.assertEqual(b"\x00\x1e", heart_rate(30))
        self.assertEqual(b"\x00\xf0", heart_rate(240))
        self.assertEqual(b"\x80\x05\x05", load.command(b"\x05\xc8\x00"))
        self.assertEqual(b"\x80\x00\x01", load.command(b"\x00"))
        for invalid in (b"\x05\xff\xff", b"\x05\xe9\x03", b"\x05\xc9\x00", b"\x05"):
            self.assertEqual(b"\x80\x05\x03", load.command(invalid))
        self.assertEqual(b"\x80\x05\x01", load.command(b"\x05\xc8\x00"))
        self.assertEqual(0, load.measurement(85)[1])
        self.assertEqual(b"\x80\x07\x01", load.command(b"\x07"))
        self.assertEqual(200, load.measurement(85)[1])
        self.assertEqual(118, load.measurement(50)[1])
        self.assertEqual(0, load.measurement(0)[1])
        self.assertEqual(b"\x80\x04\x03", load.command(b"\x04\x65\x00"))
        self.assertEqual(b"\x80\x04\x01", load.command(b"\x04\x64\x00"))
        self.assertEqual((10, 150), struct.unpack_from("<Bh", load.measurement(50)[0], 6))
        self.assertEqual(b"\x80\x08\x01", load.command(b"\x08\x02"))
        self.assertEqual(0, load.measurement(85)[1])
        self.assertEqual(b"\x80\x07\x01", load.command(b"\x07"))
        self.assertEqual(255, load.measurement(85)[1])
        self.assertEqual(b"\x80\x08\x01", load.command(b"\x08\x01"))
        self.assertIsNone(load.target_resistance)

    def test_deadline_skips_missed_periods_and_preserves_phase(self):
        self.assertEqual(10.5, next_deadline(10, 10.001, 2))
        self.assertEqual(12.5, next_deadline(10, 12.2, 2))
        self.assertEqual(12.5, next_deadline(10, 12, 2))
        self.assertAlmostEqual(12.3, next_deadline(12.2, 12.201, 10))


class RadioTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_services_subscriptions_indications_and_power_cycle(self):
        link = LocalLink()
        central_radio = Controller("central", link=link)
        central = Device.with_hci("Central", Address("F0:F1:F2:F3:00:FE"),
                                  central_radio, central_radio)
        trainer_radio = Controller("trainer", link=link)
        hrm_radio = Controller("hrm", link=link)
        trainer = Peripheral("trainer", SimpleNamespace(source=trainer_radio, sink=trainer_radio))
        hrm = Peripheral("hrm", SimpleNamespace(source=hrm_radio, sink=hrm_radio))

        async def connect(address, service_id):
            connection = await central.connect(address)
            peer = Peer(connection)
            service, = await peer.discover_service(UUID.from_16_bits(service_id))
            characteristics = await service.discover_characteristics()
            return connection, {characteristic.uuid: characteristic for characteristic in characteristics}

        async with asyncio.timeout(6):
            for device in (central, trainer.device, hrm.device):
                await device.power_on()
            self.assertEqual("Off", trainer.snapshot()["status"])
            await trainer.set_power(True)
            await hrm.set_power(True)
            trainer_link, trainer_chars = await connect(trainer.device.random_address, 0x1826)
            _, hrm_chars = await connect(hrm.device.random_address, 0x180D)
            self.assertEqual("Connected", trainer.snapshot()["status"])
            self.assertEqual(0, trainer.sent_count)
            expected_reads = {0x2ACC: "824000000c000000", 0x2AD6: "001401", 0x2AD8: "0000e8030500"}
            for short, expected in expected_reads.items():
                self.assertEqual(bytes.fromhex(expected), await trainer_chars[UUID.from_16_bits(short)].read_value())

            indications, cadence, bpm = asyncio.Queue(), asyncio.Queue(), asyncio.Queue()
            control = trainer_chars[UUID.from_16_bits(0x2AD9)]
            await control.subscribe(indications.put_nowait, prefer_notify=False)
            await trainer_chars[UUID.from_16_bits(0x2AD2)].subscribe(cadence.put_nowait)
            await hrm_chars[UUID.from_16_bits(0x2A37)].subscribe(bpm.put_nowait)
            self.assertEqual(bytes.fromhex("6400f609aa00000000"), await cadence.get())
            self.assertEqual(b"\x00\x8c", await bpm.get())
            for command, reply in (
                ("05c800", "800505"), ("00", "800001"), ("07", "800701"),
                ("05c900", "800503"), ("05c800", "800501"), ("046400", "800401"),
                ("05c800", "800501"), ("ff", "80ff02"),
            ):
                await control.write_value(bytes.fromhex(command), with_response=True)
                self.assertEqual(bytes.fromhex(reply), await indications.get())

            trainer.reading = 50
            trainer.set_rate(10)
            while (packet := await cadence.get())[4:6] != b"\x64\x00":
                pass
            self.assertEqual(118, struct.unpack_from("<h", packet, 7)[0])
            self.assertEqual(1, hrm.rate)
            address = hrm.device.random_address
            await hrm.set_power(False)
            self.assertEqual("Off", hrm.snapshot()["status"])
            self.assertEqual("Sending", trainer.snapshot()["status"])
            self.assertIs(trainer_link, central.lookup_connection(trainer_link.handle))
            await hrm.set_power(True)
            _, hrm_chars = await connect(address, 0x180D)
            hrm.reading = 160
            fresh_bpm = asyncio.Queue()
            await hrm_chars[UUID.from_16_bits(0x2A37)].subscribe(fresh_bpm.put_nowait)
            self.assertEqual(b"\x00\xa0", await fresh_bpm.get())
            await trainer.set_power(False)
            self.assertEqual("Sending", hrm.snapshot()["status"])
            self.assertIsNone(trainer.load.target_watts)
            self.assertFalse(trainer.load.controlled)
            await hrm.set_power(False)
