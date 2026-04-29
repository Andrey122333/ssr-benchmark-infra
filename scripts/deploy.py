import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


TARGETS = {
    "next": {
        "compose_dir": "deploy/next-vps",
        "services": {
            "landing": "nextjs-landing",
            "catalog": "nextjs-catalog",
        },
        "images": {
            "landing": "ghcr.io/andrey122333/nextjs-landing",
            "catalog": "ghcr.io/andrey122333/nextjs-catalog",
        },
    },
    "nuxt": {
        "compose_dir": "deploy/nuxt-vps",
        "services": {
            "landing": "nuxt-landing",
            "catalog": "nuxt-catalog",
        },
        "images": {
            "landing": "ghcr.io/andrey122333/nuxt-landing",
            "catalog": "ghcr.io/andrey122333/nuxt-catalog",
        },
    },
    "svelte": {
        "compose_dir": "deploy/svelte-vps",
        "services": {
            "landing": "sveltekit-landing",
            "catalog": "sveltekit-catalog",
        },
        "images": {
            "landing": "ghcr.io/andrey122333/sveltekit-landing",
            "catalog": "ghcr.io/andrey122333/sveltekit-catalog",
        },
    },
}


def run(cmd, check=True):
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        sys.exit(result.returncode)


def render_env(target: str, tag: str) -> str:
    cfg = TARGETS[target]

    lines = [
        f"LANDING_IMAGE={cfg['images']['landing']}:{tag}",
        f"CATALOG_IMAGE={cfg['images']['catalog']}:{tag}",
    ]

    if target == "next":
        lines += [
            "LANDING_EXTERNAL_PORT=3001",
            "CATALOG_EXTERNAL_PORT=3010",
        ]
    elif target == "nuxt":
        lines += [
            "LANDING_EXTERNAL_PORT=3002",
            "CATALOG_EXTERNAL_PORT=3012",
        ]
    elif target == "svelte":
        lines += [
            "LANDING_EXTERNAL_PORT=3003",
            "CATALOG_EXTERNAL_PORT=3013",
            "LANDING_ORIGIN=http://YOUR_SVELTE_VPS_IP:3003",
            "CATALOG_ORIGIN=http://YOUR_SVELTE_VPS_IP:3013",
        ]

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Deploy SSR benchmark stack to VPS over SSH")
    parser.add_argument("--target", choices=TARGETS.keys(), required=True, help="Target VPS: next, nuxt, svelte")
    parser.add_argument("--service", choices=["landing", "catalog", "all"], default="all", help="Service to deploy")
    parser.add_argument("--tag", default="latest", help="Docker image tag")
    parser.add_argument("--host", default=os.getenv("SSH_HOST"), help="SSH host")
    parser.add_argument("--port", default=os.getenv("SSH_PORT", "22"), help="SSH port")
    parser.add_argument("--user", default=os.getenv("SSH_USER"), help="SSH user")
    parser.add_argument("--remote-path", default=os.getenv("DEPLOY_PATH"), help="Remote deploy path")
    parser.add_argument("--ghcr-user", default=os.getenv("GHCR_USERNAME"), help="GHCR username")
    parser.add_argument("--ghcr-token", default=os.getenv("GHCR_TOKEN"), help="GHCR token")
    parser.add_argument("--write-env-only", action="store_true", help="Only generate local .env file")
    args = parser.parse_args()

    if not args.write_env_only:
        missing = []
        for key, value in {
            "host": args.host,
            "user": args.user,
            "remote_path": args.remote_path,
            "ghcr_user": args.ghcr_user,
            "ghcr_token": args.ghcr_token,
        }.items():
            if not value:
                missing.append(key)

        if missing:
            print(f"Missing required arguments/environment values: {', '.join(missing)}")
            sys.exit(1)

    target_cfg = TARGETS[args.target]
    compose_dir = Path(target_cfg["compose_dir"])
    compose_file = compose_dir / "compose.yaml"
    env_file = compose_dir / ".env"

    env_content = render_env(args.target, args.tag)
    env_file.write_text(env_content, encoding="utf-8")
    print(f"Generated {env_file}")

    if args.write_env_only:
        return

    remote_dir = f"{args.remote_path.rstrip('/')}/{args.target}"
    ssh_base = f"ssh -p {shlex.quote(str(args.port))} {shlex.quote(args.user)}@{shlex.quote(args.host)}"
    scp_base = f"scp -P {shlex.quote(str(args.port))}"

    run(f'{ssh_base} "mkdir -p {shlex.quote(remote_dir)}"')

    run(f"{scp_base} {shlex.quote(str(compose_file))} {shlex.quote(str(env_file))} "
        f"{shlex.quote(args.user)}@{shlex.quote(args.host)}:{shlex.quote(remote_dir)}/")

    login_cmd = (
        f"echo {shlex.quote(args.ghcr_token)} | "
        f"docker login ghcr.io -u {shlex.quote(args.ghcr_user)} --password-stdin"
    )

    if args.service == "all":
        compose_cmd = "docker compose pull && docker compose up -d"
    else:
        service_name = target_cfg["services"][args.service]
        other_service_key = "catalog" if args.service == "landing" else "landing"
        other_service_name = target_cfg["services"][other_service_key]
        compose_cmd = (
            f"docker compose pull {shlex.quote(service_name)} && "
            f"docker compose up -d {shlex.quote(service_name)} && "
            f"docker compose stop {shlex.quote(other_service_name)}"
        )

    remote_script = f"""
        set -e
        cd {shlex.quote(remote_dir)}
        {login_cmd}
        {compose_cmd}
        docker compose ps
    """.strip()

    run(f'{ssh_base} "{remote_script}"')


if __name__ == "__main__":
    main()
