#!/usr/bin/env python3
"""Listen on wss:8443 and decode takproto frames; report any sikw00f events —
confirms whether the sentinel's wss TX actually reaches TAK."""
import asyncio
import ssl
import sys
import time

import aiohttp
from takproto import parse_proto

URL = "wss://takserver.snstak.com:8443/takproto/1"
CERT = "/etc/sikw00fcot/sikw00fcot.pem"
KEY = "/etc/sikw00fcot/sikw00fcot-key.pem"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 35


def ctx():
    c = ssl.create_default_context()
    c.load_cert_chain(CERT, KEY)
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


async def main():
    t0 = time.time()
    seen = {}
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(URL, ssl=ctx(), heartbeat=None) as ws:
            while time.time() - t0 < LIMIT:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=LIMIT)
                except asyncio.TimeoutError:
                    break
                if msg.type != aiohttp.WSMsgType.BINARY:
                    continue
                try:
                    tak = parse_proto(msg.data)
                    xml = tak if isinstance(tak, bytes) else None
                    text = xml.decode("utf-8", "replace") if xml else str(tak)
                except Exception:
                    text = str(msg.data)
                if "sikw00f" in text:
                    import re
                    for u in re.findall(r'uid[=:"\' ]+(sikw00f[\w-]*)', text):
                        seen[u] = seen.get(u, 0) + 1
    print("sikw00f events received over wss:8443:")
    for u, n in sorted(seen.items()):
        print(f"  {n:3d}  {u}")
    if not seen:
        print("  NONE")


asyncio.run(main())
