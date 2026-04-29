import argparse
import sys
import time
import urllib.error
import urllib.request


def check_once(url: str, timeout: int) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ssr-benchmark-healthcheck/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            if 200 <= status < 400:
                return True, f"OK ({status})"
            return False, f"Unexpected status: {status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP error: {e.code}"
    except urllib.error.URLError as e:
        return False, f"URL error: {e.reason}"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    parser = argparse.ArgumentParser(description="HTTP healthcheck for deployed SSR app")
    parser.add_argument("--url", required=True, help="URL to check")
    parser.add_argument("--attempts", type=int, default=10, help="Number of attempts")
    parser.add_argument("--delay", type=int, default=5, help="Delay between attempts in seconds")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP timeout in seconds")
    args = parser.parse_args()

    for attempt in range(1, args.attempts + 1):
        ok, message = check_once(args.url, args.timeout)
        print(f"[{attempt}/{args.attempts}] {args.url} -> {message}")

        if ok:
            print("Healthcheck passed.")
            sys.exit(0)

        if attempt < args.attempts:
            time.sleep(args.delay)

    print("Healthcheck failed.")
    sys.exit(1)


if __name__ == "__main__":
    main()
