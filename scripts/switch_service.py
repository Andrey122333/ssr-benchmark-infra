import argparse
import os
import shlex
import subprocess
import sys


TARGETS = {
    "next": {
        "services": {
            "landing": "nextjs-landing",
            "catalog": "nextjs-catalog",
        },
    },
    "nuxt": {
        "services": {
            "landing": "nuxt-landing",
            "catalog": "nuxt-catalog",
        },
    },
    "svelte": {
        "services": {
            "landing": "sveltekit-landing",
            "catalog": "sveltekit-catalog",
        },
    },
}


def run(cmd, check=True):
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Switch active service on VPS")
    parser.add_argument("--target", choices=TARGETS.keys(), required=True)
    parser.add_argument("--service", choices=["landing", "catalog"], required=True)
    parser.add_argument("--host", default=os.getenv("SSH_HOST"))
    parser.add_argument("--port", default=os.getenv("SSH_PORT", "22"))
    parser.add_argument("--user", default=os.getenv("SSH_USER"))
    parser.add_argument("--remote-path", default=os.getenv("DEPLOY_PATH"))
    parser.add_argument("--ssh-key", default=os.getenv("SSH_KEY_PATH"))
    args = parser.parse_args()

    missing = []
    for key, value in {
        "host": args.host,
        "user": args.user,
        "remote_path": args.remote_path,
    }.items():
        if not value:
            missing.append(key)

    if missing:
        print(f"Missing required arguments/environment values: {', '.join(missing)}")
        sys.exit(1)

    target_cfg = TARGETS[args.target]
    active_service = target_cfg["services"][args.service]
    passive_key = "catalog" if args.service == "landing" else "landing"
    passive_service = target_cfg["services"][passive_key]

    remote_dir = f"{args.remote_path.rstrip('/')}/{args.target}"
    key_opt = f"-i {shlex.quote(args.ssh_key)}" if args.ssh_key else ""
    ssh_base = (
        f"ssh -p {shlex.quote(str(args.port))} "
        f"{key_opt} "
        f"{shlex.quote(args.user)}@{shlex.quote(args.host)}"
    )

    remote_script = f"""
        set -e
        cd {shlex.quote(remote_dir)}
        docker compose up -d {shlex.quote(active_service)}
        docker compose stop {shlex.quote(passive_service)}
        docker compose ps
    """.strip()

    run(f'{ssh_base} "{remote_script}"')


if __name__ == "__main__":
    main()
