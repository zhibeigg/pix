from __future__ import annotations

import argparse
import asyncio

import uvicorn

from pix_updater.api import app


async def _serve(host: str, port: int) -> None:
    config = uvicorn.Config(app, host=host, port=port, proxy_headers=False, access_log=False)
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the internal Pix update agent.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    asyncio.run(_serve(args.host, args.port))


if __name__ == "__main__":
    main()
