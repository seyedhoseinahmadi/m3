# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, os
from pathlib import Path

APP_VERSION = "CUSTOMER-FINAL-INSTALLER-0.4.7"

def clean_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValueError("Server URL must start with https:// or http://")
    return url

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-url", default=os.getenv("HOZOOR_SERVER_URL", ""))
    parser.add_argument("--server-id", default=os.getenv("HOZOOR_SERVER_ID", ""))
    parser.add_argument("--agent-token", default=os.getenv("HOZOOR_AGENT_TOKEN", ""))
    parser.add_argument("--directory-api-url", default=os.getenv("HIMATE_DIRECTORY_API_URL", "https://mangroup.ir"))
    parser.add_argument("--directory-api-token", default=os.getenv("HIMATE_DIRECTORY_API_TOKEN", ""))
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args()

    server_url = args.server_url.strip()
    server_id = args.server_id.strip()
    token = args.agent_token.strip()
    directory_api_url = args.directory_api_url.strip() or "https://mangroup.ir"
    directory_api_token = args.directory_api_token.strip()

    if not args.non_interactive:
        print()
        print("HiMate Customer Final UI Build Config")
        print("--------------------------------------")
        print("Server URL is compiled into EXE and is not editable in customer build.")
        print("Windows app is NOT locked to a device. Device code is read from device.")
        print()
        if not server_url:
            server_url = input("Server URL, example https://hozoor.example.com: ").strip()
        if not server_id:
            server_id = input("Server ID (required): ").strip()
        if not token:
            token = input("Agent Token (optional): ").strip()

    if not server_id:
        raise ValueError("HOZOOR_SERVER_ID is required. Set it in GitHub Repository Variables or pass --server-id.")

    server_url = clean_url(server_url)
    directory_api_url = clean_url(directory_api_url)
    content = f'''# -*- coding: utf-8 -*-
APP_VERSION = "CUSTOMER-FINAL-INSTALLER-0.4.7"
APP_NAME = "HiMate Sync"
SERVER_URL = {server_url!r}
SERVER_ID = {server_id!r}
AGENT_TOKEN = {token!r}
DIRECTORY_API_URL = {directory_api_url!r}
DIRECTORY_API_TOKEN = {directory_api_token!r}
BUILD_CHANNEL = "customer-final-installer"
'''
    Path("hozoor_customer_build_config.py").write_text(content, encoding="utf-8")
    print("Generated hozoor_customer_build_config.py")
    print("SERVER_URL =", server_url)
    print("SERVER_ID  =", server_id)
    print("DIRECTORY_API_URL =", directory_api_url)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
