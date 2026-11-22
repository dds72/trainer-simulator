"""Loopback HTTP control panel and Bumble transport setup."""

import argparse
import asyncio
import logging
from contextlib import AsyncExitStack
from pathlib import Path

from aiohttp import web
from bumble.transport import open_transport
from bumble.transport.android_netsim import find_grpc_port

from .measurements import RATES
from .peripheral import Peripheral

LOG = logging.getLogger("trainer_simulator")
WEB = Path(__file__).with_name("web")
DEVICES = web.AppKey("devices", dict)


def loopback_endpoint(value):
    host, separator, port = value.rpartition(":")
    if not separator or host not in ("localhost", "127.0.0.1", "[::1]"):
        raise argparse.ArgumentTypeError("expected a loopback HOST:PORT")
    return f"{host}:{port_number(port)}"


def port_number(value):
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535:
        raise argparse.ArgumentTypeError("expected a port from 1 to 65535")
    return int(value)


def transport_specs(args):
    if args.trainer_usb:
        return {"trainer": f"usb:{args.trainer_usb}", "hrm": f"usb:{args.hrm_usb}"}
    endpoint = args.netsim_endpoint
    if endpoint is None:
        port = find_grpc_port(0)
        if not port:
            raise RuntimeError("Netsim discovery failed. Start the AVD or pass --netsim-endpoint HOST:PORT.")
        endpoint = f"localhost:{port}"
    LOG.info("Netsim endpoint %s", endpoint)
    return {role: f"android-netsim:{endpoint},name=trainer-simulator-{role}"
            for role in ("trainer", "hrm")}


async def watch_transport(device, transport):
    await asyncio.shield(transport.source.terminated)
    await device.on_transport_lost()


async def close_device(device):
    try:
        if not device.transport_lost:
            await asyncio.wait_for(device.set_power(False), 5)
    except Exception:
        LOG.exception("Could not shut down %s", device.name)
    finally:
        tasks = list(device.background)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def stop_watcher(task):
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def make_app(specs):
    app = web.Application(client_max_size=4096)
    app[DEVICES] = {}

    async def bluetooth(app):
        async with AsyncExitStack() as stack:
            for role, spec in specs.items():
                try:
                    async with asyncio.timeout(8):
                        transport = await open_transport(spec)
                        stack.push_async_callback(transport.close)
                        device = Peripheral(role, transport)
                        await device.device.power_on()
                except Exception as error:
                    reason = str(error) or type(error).__name__
                    raise RuntimeError(f"Could not start {role} on {spec}: {reason}") from error
                stack.push_async_callback(close_device, device)
                watcher = asyncio.create_task(watch_transport(device, transport))
                stack.push_async_callback(stop_watcher, watcher)
                app[DEVICES][role] = device
                LOG.info("%s ready (Off)", device.name)
            yield

    app.cleanup_ctx.append(bluetooth)
    app.router.add_get("/", index)
    app.router.add_get("/api/devices", devices)
    app.router.add_patch("/api/devices/{role}", update_device)
    app.router.add_static("/assets/", WEB / "assets")
    return app


async def index(_request):
    return web.FileResponse(WEB / "index.html")


async def devices(request):
    return web.json_response({role: device.snapshot() for role, device in request.app[DEVICES].items()})


async def update_device(request):
    if request.host.partition(":")[0] not in ("127.0.0.1", "localhost"):
        raise web.HTTPForbidden(text="Use the simulator's loopback address.")
    origin = request.headers.get("Origin")
    if origin is not None and origin != f"http://{request.host}":
        raise web.HTTPForbidden(text="Use the simulator's local control panel.")
    device = request.app[DEVICES].get(request.match_info["role"])
    if device is None:
        raise web.HTTPNotFound(text="Unknown peripheral.")
    if request.content_type != "application/json":
        raise web.HTTPUnsupportedMediaType(text="Use application/json.")
    try:
        update = await request.json()
    except ValueError:
        raise web.HTTPBadRequest(text="Invalid JSON.") from None
    if not isinstance(update, dict) or len(update) != 1:
        raise web.HTTPBadRequest(text="Send one setting at a time.")
    field, value = next(iter(update.items()))
    if field == "enabled" and type(value) is bool:
        if device.transport_lost:
            raise web.HTTPServiceUnavailable(text="Bluetooth transport lost. Restart the simulator.")
        try:
            await asyncio.wait_for(device.set_power(value), 5)
        except Exception as error:
            device.error = str(error) or type(error).__name__
            LOG.exception("Power change failed for %s", device.name)
            raise web.HTTPServiceUnavailable(text=f"{device.name}: {device.error}") from error
    elif field == "reading" and type(value) is int and device.minimum <= value <= device.maximum:
        device.reading = value
    elif field == "rate" and type(value) in (int, float) and value in RATES:
        device.set_rate(value)
    else:
        raise web.HTTPBadRequest(text="Invalid setting or value.")
    return web.json_response(device.snapshot())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=port_number, default=8765, help="loopback HTTP port")
    parser.add_argument("--netsim-endpoint", type=loopback_endpoint, metavar="HOST:PORT",
                        help="override automatic Netsim discovery")
    parser.add_argument("--trainer-usb", metavar="SELECTOR", help="Bumble USB selector for trainer")
    parser.add_argument("--hrm-usb", metavar="SELECTOR", help="Bumble USB selector for HRM")
    args = parser.parse_args()
    if args.trainer_usb is not None or args.hrm_usb is not None:
        if not args.trainer_usb or not args.hrm_usb or args.trainer_usb == args.hrm_usb:
            parser.error("USB mode requires two distinct controller selectors")
        if args.netsim_endpoint:
            parser.error("choose USB controllers or a Netsim endpoint")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        web.run_app(make_app(transport_specs(args)), host="127.0.0.1", port=args.port,
                    access_log=None)
    except (RuntimeError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
