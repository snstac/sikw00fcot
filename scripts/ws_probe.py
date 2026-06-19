#!/usr/bin/env python3
"""Probe the TAK wss:8443 takproto endpoint: capture close code + timing, and
test whether client heartbeat pings keep the connection alive."""
import asyncio
import ssl
import time

import aiohttp

URL = "wss://takserver.snstak.com:8443/takproto/1"
CERT = "/etc/sikw00fcot/sikw00fcot.pem"
KEY = "/etc/sikw00fcot/sikw00fcot-key.pem"


def ctx():
    c = ssl.create_default_context()
    c.load_cert_chain(CERT, KEY)
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


async def run(hb, limit):
    t0 = time.time()
    msgs = 0
    label = f"heartbeat={hb}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(URL, ssl=ctx(), heartbeat=hb) as ws:
                print(f"[{label}] connected at {time.time()-t0:.1f}s")
                while time.time() - t0 < limit:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=limit)
                    except asyncio.TimeoutError:
                        break
                    if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING,
                                    aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        print(f"[{label}] CLOSED type={msg.type.name} "
                              f"close_code={ws.close_code} at {time.time()-t0:.1f}s "
                              f"(after {msgs} msgs)")
                        return
                    msgs += 1
                print(f"[{label}] still UP at {time.time()-t0:.1f}s "
                      f"({msgs} msgs) close_code={ws.close_code}")
    except Exception as exc:
        print(f"[{label}] exception {type(exc).__name__}: {exc} at {time.time()-t0:.1f}s")


async def main():
    print("=== A: NO client heartbeat ===")
    await run(None, 40)
    print("=== B: client heartbeat every 10s ===")
    await run(10, 50)


asyncio.run(main())
