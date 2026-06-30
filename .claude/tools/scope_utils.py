from __future__ import annotations

import re
from urllib.parse import urlparse


NETWORK_TOOLS = {
    "curl",
    "wget",
    "nc",
    "netcat",
    "nmap",
    "ffuf",
    "sqlmap",
    "nikto",
    "httpx",
    "python",
    "python3",
}

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def command_hosts(command: str) -> list[str]:
    hosts = []
    for value in re.findall(r"https?://[^\s'\"<>]+", command):
        host = urlparse(value).hostname
        if host and host not in hosts:
            hosts.append(host)
    for value in re.findall(r"(?<![\w.-])(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?![\w.-])", command):
        host = value.split(":", 1)[0]
        if host not in hosts:
            hosts.append(host)
    for value in re.findall(r"(?<![-\w])(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d+)?", command):
        host = value.split(":", 1)[0]
        if host not in hosts:
            hosts.append(host)
    return hosts


def command_uses_network_tool(command: str) -> bool:
    first = command.strip().split(maxsplit=1)[0] if command.strip() else ""
    return first in NETWORK_TOOLS or any(f" {tool} " in f" {command} " for tool in NETWORK_TOOLS)


def hosts_in_scope(command: str, allowed_scope: dict) -> tuple[bool, str]:
    hosts = command_hosts(command)
    if not hosts:
        return True, "no external host detected"
    allowed_hosts = set(allowed_scope.get("hosts", [])) | LOCAL_HOSTS
    targets = " ".join(allowed_scope.get("targets", []) + allowed_scope.get("urls", []))
    for host in hosts:
        if host in allowed_hosts or host in targets:
            continue
        return False, f"host {host} is outside challenge scope"
    return True, "all detected hosts are in scope"


def looks_like_large_scan(command: str) -> bool:
    lowered = command.lower()
    return any(token in lowered for token in ["/0", "/8", "0.0.0.0/0"]) or (
        "nmap" in lowered and ("-p-" in lowered or "--top-ports" in lowered) and not any(host in lowered for host in LOCAL_HOSTS)
    )
