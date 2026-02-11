#!/usr/bin/env python3
"""
Deploy script for contest project.

Usage:
    python deploy.py --all                   # deploy everything
    python deploy.py --backend               # backend + worker + scheduler
    python deploy.py --bot                   # bot only
    python deploy.py --watcher               # watcher only
    python deploy.py --backend --bot         # combine targets
    python deploy.py --files path1 path2     # specific files only
    python deploy.py --backend --no-rebuild  # upload without docker rebuild
    python deploy.py --backend --restart-only  # rebuild without uploading files

Environment variables (or prompted interactively):
    DEPLOY_HOST       server IP (default: 85.239.58.214)
    DEPLOY_USER       SSH user (default: root)
    DEPLOY_PASSWORD   SSH password
    DEPLOY_PATH       project path on server (default: /opt/contest)
"""

import argparse
import getpass
import os
import posixpath
import sys
import time

try:
    import paramiko
except ImportError:
    print("paramiko not installed. Run: pip install paramiko")
    sys.exit(1)


DEFAULT_HOST = "85.239.58.214"
DEFAULT_USER = "root"
DEFAULT_PATH = "/opt/contest"

BACKEND_FILES = [
    "backend/",
    "requirements.txt",
]

BOT_FILES = [
    "bot/",
]

WATCHER_FILES = [
    "watcher/",
]

INFRA_FILES = [
    "docker-compose.yml",
    "Dockerfile",
    "Caddyfile",
]

BACKEND_SERVICES = ["backend", "worker", "scheduler"]
BOT_SERVICES = ["bot"]
WATCHER_SERVICES = ["watcher"]
INFRA_SERVICES = ["caddy"]

LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

IGNORE_PATTERNS = [
    "__pycache__",
    ".pyc",
    "node_modules",
    ".git",
    ".env",
    ".venv",
    "venv",
    ".pytest_cache",
    "dist",
    "build",
    ".DS_Store",
    "*.log",
]


def should_ignore(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    for part in parts:
        for pattern in IGNORE_PATTERNS:
            if pattern.startswith("*"):
                if part.endswith(pattern[1:]):
                    return True
            elif part == pattern:
                return True
    return False


def collect_files(paths: list[str]) -> list[str]:
    result = []
    for rel_path in paths:
        abs_path = os.path.join(LOCAL_ROOT, rel_path)
        if os.path.isdir(abs_path):
            for root, dirs, files in os.walk(abs_path):
                dirs[:] = [d for d in dirs if not should_ignore(d)]
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, LOCAL_ROOT).replace("\\", "/")
                    if not should_ignore(rel):
                        result.append(rel)
        elif os.path.isfile(abs_path):
            rel = rel_path.replace("\\", "/")
            if not should_ignore(rel):
                result.append(rel)
        else:
            print(f"  [WARN] Not found: {rel_path}")
    return sorted(set(result))


def run_ssh(ssh: paramiko.SSHClient, command: str, timeout: int = 300) -> tuple[int, str, str]:
    stdin, stdout, stderr = ssh.exec_command(command, get_pty=True, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def strip_ansi(text: str) -> str:
    import re
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\[\?[0-9]*[a-zA-Z]", "", text)


def connect(host: str, user: str, password: str) -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=host,
        username=user,
        password=password,
        timeout=20,
        banner_timeout=20,
        auth_timeout=20,
        look_for_keys=False,
        allow_agent=False,
    )
    return ssh


def verify_server(ssh: paramiko.SSHClient, remote_path: str) -> bool:
    code, _, _ = run_ssh(ssh, f"test -f {remote_path}/docker-compose.yml")
    return code == 0


def upload_files(ssh: paramiko.SSHClient, remote_path: str, files: list[str]) -> int:
    sftp = ssh.open_sftp()
    ts = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    uploaded = 0

    created_dirs: set[str] = set()

    for rel in files:
        local_path = os.path.join(LOCAL_ROOT, rel)
        remote_file = posixpath.join(remote_path, rel)
        remote_dir = posixpath.dirname(remote_file)

        if remote_dir not in created_dirs:
            run_ssh(ssh, f"mkdir -p {remote_dir}")
            created_dirs.add(remote_dir)

        code, _, _ = run_ssh(ssh, f"test -f {remote_file}")
        if code == 0:
            backup = f"{remote_file}.bak-{ts}"
            run_ssh(ssh, f"cp {remote_file} {backup}")

        sftp.put(local_path, remote_file)
        uploaded += 1
        print(f"  [{uploaded}/{len(files)}] {rel}")

    sftp.close()
    return uploaded


def rebuild_services(ssh: paramiko.SSHClient, remote_path: str, services: list[str]) -> bool:
    services_str = " ".join(services)
    print(f"\n  Rebuilding: {services_str}")
    code, out, err = run_ssh(ssh, f"cd {remote_path} && docker compose up -d --build {services_str}", timeout=600)
    clean_out = strip_ansi(out + err).strip()

    for line in clean_out.split("\n"):
        line = line.strip()
        if line and ("Built" in line or "Started" in line or "Recreated" in line
                     or "Running" in line or "Healthy" in line or "error" in line.lower()
                     or "Error" in line):
            print(f"  {line}")

    if code != 0:
        print(f"\n  [ERROR] docker compose exited with code {code}")
        return False
    return True


def check_status(ssh: paramiko.SSHClient, remote_path: str, services: list[str]) -> None:
    services_str = " ".join(services)
    code, out, err = run_ssh(ssh, f"cd {remote_path} && docker compose ps {services_str}")
    clean = strip_ansi(out).strip()
    if clean:
        print(f"\n{clean}")

    for svc in services:
        code, out, err = run_ssh(ssh, f"cd {remote_path} && docker compose logs --tail=10 {svc}")
        clean = strip_ansi(out).strip()
        if clean:
            lines = clean.split("\n")
            print(f"\n  --- {svc} (last {min(10, len(lines))} lines) ---")
            for line in lines[-10:]:
                print(f"  {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy contest project to server")
    parser.add_argument("--all", action="store_true", help="Deploy everything")
    parser.add_argument("--backend", action="store_true", help="Deploy backend + worker + scheduler")
    parser.add_argument("--bot", action="store_true", help="Deploy bot")
    parser.add_argument("--watcher", action="store_true", help="Deploy watcher")
    parser.add_argument("--infra", action="store_true", help="Deploy docker-compose.yml, Dockerfile, Caddyfile")
    parser.add_argument("--files", nargs="+", help="Deploy specific files (relative paths)")
    parser.add_argument("--no-rebuild", action="store_true", help="Upload files without docker rebuild")
    parser.add_argument("--restart-only", action="store_true", help="Rebuild without uploading files")
    parser.add_argument("--host", default=os.environ.get("DEPLOY_HOST", DEFAULT_HOST))
    parser.add_argument("--user", default=os.environ.get("DEPLOY_USER", DEFAULT_USER))
    parser.add_argument("--password", default=os.environ.get("DEPLOY_PASSWORD", ""))
    parser.add_argument("--path", default=os.environ.get("DEPLOY_PATH", DEFAULT_PATH))
    args = parser.parse_args()

    if not any([args.all, args.backend, args.bot, args.watcher, args.infra, args.files, args.restart_only]):
        parser.print_help()
        return 1

    password = args.password
    if not password:
        password = getpass.getpass(f"SSH password for {args.user}@{args.host}: ")

    file_paths: list[str] = []
    services: list[str] = []

    if args.all:
        file_paths = BACKEND_FILES + BOT_FILES + WATCHER_FILES + INFRA_FILES
        services = BACKEND_SERVICES + BOT_SERVICES + WATCHER_SERVICES + INFRA_SERVICES
    else:
        if args.backend:
            file_paths += BACKEND_FILES
            services += BACKEND_SERVICES
        if args.bot:
            file_paths += BOT_FILES
            services += BOT_SERVICES
        if args.watcher:
            file_paths += WATCHER_FILES
            services += WATCHER_SERVICES
        if args.infra:
            file_paths += INFRA_FILES
            services += INFRA_SERVICES
        if args.files:
            file_paths += args.files

    services = list(dict.fromkeys(services))

    print(f"\n=== Deploy to {args.user}@{args.host}:{args.path} ===\n")

    print("Connecting...")
    try:
        ssh = connect(args.host, args.user, password)
    except Exception as e:
        print(f"  [ERROR] SSH connection failed: {e}")
        return 1

    if not verify_server(ssh, args.path):
        print(f"  [ERROR] docker-compose.yml not found at {args.path}")
        ssh.close()
        return 1
    print(f"  Server OK: {args.path}")

    if not args.restart_only and file_paths:
        print("\nCollecting files...")
        files = collect_files(file_paths)
        if not files:
            print("  No files to upload")
        else:
            print(f"  Found {len(files)} files\n")
            print("Uploading...")
            uploaded = upload_files(ssh, args.path, files)
            print(f"\n  Uploaded {uploaded} files")

    if services and not args.no_rebuild:
        print("\nRebuilding containers...")
        ok = rebuild_services(ssh, args.path, services)
        if not ok:
            ssh.close()
            return 1

        print("\nChecking status...")
        check_status(ssh, args.path, services)

    print("\n=== Deploy complete ===\n")
    ssh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
