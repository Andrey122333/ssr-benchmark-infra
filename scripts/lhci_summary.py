#!/usr/bin/env python3
"""
lhci_summary.py — печатает сводку Lighthouse assertion-results.json в лог GitHub Actions.
Использование:
  python scripts/lhci_summary.py --results .lighthouseci/assertion-results.json \
    --target next --service catalog
"""

import argparse
import json
import sys
from pathlib import Path

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"

METRIC_LABELS = {
    "categories": "Score",
    "first-contentful-paint": "FCP",
    "largest-contentful-paint": "LCP",
    "speed-index": "Speed Index",
    "interactive": "TTI",
    "total-blocking-time": "TBT",
    "cumulative-layout-shift": "CLS",
    "server-response-time": "TTFB",
    "experimental-interaction-to-next-paint": "INP",
}

AUDIT_PROPERTY_LABELS = {
    "performance": "Performance",
    "accessibility": "Accessibility",
    "best-practices": "Best Practices",
    "seo": "SEO",
}


def fmt_value(v):
    if isinstance(v, float):
        return f"{v:.1f}" if v > 1 else f"{v:.2f}"
    return str(v)


def parse_results(path: Path):
    if not path.exists():
        print(f"{YELLOW}⚠ assertion-results.json not found at {path}{RESET}")
        sys.exit(0)

    with path.open() as f:
        data = json.load(f)

    results = data if isinstance(data, list) else data.get("results", [])
    return results


def print_summary(results, target, service):
    passed = [r for r in results if r.get("passed")]
    failed = [r for r in results if not r.get("passed")]

    print()
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Lighthouse Summary — {target.upper()} / {service.upper()}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"  Total assertions : {len(results)}")
    print(f"  {GREEN}Passed{RESET}           : {len(passed)}")
    print(f"  {RED}Failed{RESET}           : {len(failed)}")
    print(f"{BOLD}{'-'*60}{RESET}")

    # Группируем по URL
    urls = {}
    for r in results:
        url = r.get("url", "unknown")
        urls.setdefault(url, []).append(r)

    for url, assertions in urls.items():
        print(f"\n  URL: {url}")
        print(f"  {'-'*54}")

        for r in assertions:
            ok = r.get("passed", False)
            icon = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"

            audit_id = r.get("auditId", "")
            audit_prop = r.get("auditProperty", "")
            name = r.get("name", "")

            # Метка метрики
            if audit_id == "categories" and audit_prop:
                label = AUDIT_PROPERTY_LABELS.get(audit_prop, audit_prop)
            else:
                label = METRIC_LABELS.get(audit_id, audit_id or name)

            expected = r.get("expected")
            actual = r.get("actual")
            operator = r.get("operator", "")
            values = r.get("values", [])

            exp_str = fmt_value(expected) if expected is not None else "—"
            act_str = fmt_value(actual) if actual is not None else "—"

            if values and len(values) > 1:
                vals_str = f"  runs: [{', '.join(fmt_value(v) for v in values)}]"
            else:
                vals_str = ""

            print(f"  {icon}  {label:<22} expected {operator}{exp_str:<8} actual {act_str}{vals_str}")

    print()
    if failed:
        print(f"{RED}{BOLD}  ✗ {len(failed)} assertion(s) failed{RESET}")
        sys.exit(1)
    else:
        print(f"{GREEN}{BOLD}  ✓ All assertions passed{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--target", default="unknown")
    parser.add_argument("--service", default="unknown")
    args = parser.parse_args()

    results = parse_results(Path(args.results))
    print_summary(results, args.target, args.service)


if __name__ == "__main__":
    main()
