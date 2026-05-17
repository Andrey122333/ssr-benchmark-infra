#!/usr/bin/env python3
"""
k6 JSON output degradation analyzer
Стримит файл построчно (работает даже с 150 МБ+ файлами).
Детектирует деградацию RPS и латентности по скользящему окну.

Использование:
    python3 analyze_k6.py results.json
    python3 analyze_k6.py results.json --window 10 --rps-drop 0.3 --latency-spike 2.0
    python3 analyze_k6.py results.json --scenario landing_baseline --endpoint landing_home
    python3 analyze_k6.py results.json --csv metrics.csv
"""

import json
import sys
import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone


def parse_args():
    p = argparse.ArgumentParser(description="k6 degradation detector")
    p.add_argument("file", help="Путь к results.json (k6 --out json=)")
    p.add_argument("--window", type=int, default=10,
                   help="Размер скользящего окна в секундах (default: 10)")
    p.add_argument("--rps-drop", type=float, default=0.30,
                   help="Порог падения RPS от baseline (0.30 = -30%%, default: 0.30)")
    p.add_argument("--latency-spike", type=float, default=2.0,
                   help="Множитель латентности от baseline для тревоги (default: 2.0)")
    p.add_argument("--error-rate", type=float, default=0.05,
                   help="Порог error rate (default: 0.05 = 5%%)")
    p.add_argument("--scenario", default=None,
                   help="Фильтр по scenario (опционально)")
    p.add_argument("--endpoint", default=None,
                   help="Фильтр по name/endpoint (опционально)")
    p.add_argument("--baseline-warmup", type=int, default=30,
                   help="Первые N секунд считаются baseline (default: 30)")
    p.add_argument("--csv", default=None,
                   help="Сохранить посекундные метрики в CSV (опционально)")
    return p.parse_args()


def ts_to_epoch(ts_str: str) -> float:
    """ISO8601 с наносекундами → unix float."""
    ts_str = ts_str.rstrip("Z")
    if "." in ts_str:
        date_part, frac = ts_str.split(".", 1)
        frac = frac[:6]
        ts_str = f"{date_part}.{frac}"
    dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S.%f")
    return dt.replace(tzinfo=timezone.utc).timestamp()


def fmt_time(epoch: float) -> str:
    return datetime.utcfromtimestamp(epoch).strftime("%H:%M:%S")


def percentile(data, p):
    if not data:
        return 0
    s = sorted(data)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s) - 1)]


def analyze(args):
    buckets = defaultdict(lambda: {"reqs": 0, "errors": 0, "durations": []})

    print(f"[*] Читаем {args.file} (стриминг, RAM-friendly)...")
    lines_read = 0
    points_used = 0

    with open(args.file, "r", buffering=1 << 20) as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            lines_read += 1
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if obj.get("type") != "Point":
                continue

            metric = obj.get("metric", "")
            data = obj.get("data", {})
            tags = data.get("tags", {})

            if args.scenario and tags.get("scenario") != args.scenario:
                continue
            if args.endpoint and tags.get("name") != args.endpoint:
                continue

            try:
                epoch = ts_to_epoch(data["time"])
            except Exception:
                continue

            bk = int(epoch)  # посекундные бакеты

            if metric == "http_reqs":
                buckets[bk]["reqs"] += data.get("value", 0)
                points_used += 1
            elif metric == "http_req_duration":
                buckets[bk]["durations"].append(data.get("value", 0))
                points_used += 1
            elif metric == "http_req_failed":
                buckets[bk]["errors"] += data.get("value", 0)
                points_used += 1

    print(f"[*] Прочитано строк: {lines_read:,} | использовано точек: {points_used:,}")

    if not buckets:
        print("[!] Нет данных. Проверь фильтры --scenario / --endpoint.")
        return

    sorted_keys = sorted(buckets.keys())
    t0 = sorted_keys[0]
    t_end = sorted_keys[-1]
    duration_s = t_end - t0

    print(f"[*] Диапазон: {fmt_time(t0)} – {fmt_time(t_end)} ({duration_s:.0f}s)")
    print(f"[*] Окно: {args.window}s | baseline warmup: {args.baseline_warmup}s\n")

    # Посекундные агрегаты
    rows = []
    for bk in sorted_keys:
        b = buckets[bk]
        reqs = b["reqs"]
        errs = b["errors"]
        durs = b["durations"]
        avg = sum(durs) / len(durs) if durs else 0
        p50 = percentile(durs, 50)
        p95 = percentile(durs, 95)
        error_rate = errs / reqs if reqs > 0 else 0
        rows.append({
            "epoch": bk,
            "time": fmt_time(bk),
            "elapsed": bk - t0,
            "rps": reqs,
            "p50": round(p50, 1),
            "p95": round(p95, 1),
            "avg_ms": round(avg, 1),
            "error_rate": round(error_rate, 4),
        })

    # Baseline
    baseline_rows = [r for r in rows if r["elapsed"] <= args.baseline_warmup]
    if not baseline_rows:
        baseline_rows = rows[:max(1, len(rows) // 5)]

    bl_rps = sum(r["rps"] for r in baseline_rows) / len(baseline_rows)
    bl_lat_vals = [r["avg_ms"] for r in baseline_rows if r["avg_ms"] > 0]
    bl_lat = sum(bl_lat_vals) / len(bl_lat_vals) if bl_lat_vals else 1

    rps_threshold = bl_rps * (1 - args.rps_drop)
    lat_threshold = bl_lat * args.latency_spike

    print(f"[baseline]   avg RPS = {bl_rps:.1f} req/s | avg latency = {bl_lat:.1f} ms")
    print(f"[thresholds] RPS < {rps_threshold:.1f} → alert | latency > {lat_threshold:.0f}ms → alert | error > {args.error_rate*100:.0f}%")
    print("-" * 70)

    # Скользящее окно + детектор деградации
    window = deque()
    degradation_events = []
    in_degradation = False
    deg_start = None

    for row in rows:
        window.append(row)
        while window and row["elapsed"] - window[0]["elapsed"] >= args.window:
            window.popleft()

        if not window:
            continue

        w_rps = sum(r["rps"] for r in window) / len(window)
        w_lat_vals = [r["avg_ms"] for r in window if r["avg_ms"] > 0]
        w_lat = sum(w_lat_vals) / len(w_lat_vals) if w_lat_vals else 0
        w_err = sum(r["error_rate"] for r in window) / len(window)

        past_warmup = row["elapsed"] > args.baseline_warmup
        is_rps_low  = past_warmup and w_rps < rps_threshold
        is_lat_high = past_warmup and w_lat > lat_threshold
        is_err_high = w_err > args.error_rate

        is_degraded = is_rps_low or is_lat_high or is_err_high

        reasons = []
        if is_rps_low:
            reasons.append(f"RPS {w_rps:.1f} (< {rps_threshold:.1f})")
        if is_lat_high:
            reasons.append(f"Latency {w_lat:.0f}ms (> {lat_threshold:.0f}ms)")
        if is_err_high:
            reasons.append(f"Errors {w_err*100:.1f}% (> {args.error_rate*100:.0f}%)")

        if is_degraded and not in_degradation:
            in_degradation = True
            deg_start = row["epoch"]
            degradation_events.append({
                "start": row["time"],
                "elapsed_s": int(row["elapsed"]),
                "rps": round(w_rps, 1),
                "latency_ms": round(w_lat, 0),
                "error_pct": round(w_err * 100, 1),
                "reasons": reasons,
            })
            print(f"🔴 ДЕГРАДАЦИЯ  @ {row['time']} (+{int(row['elapsed'])}s) | " + " | ".join(reasons))

        elif not is_degraded and in_degradation:
            in_degradation = False
            duration_deg = row["epoch"] - deg_start
            print(f"🟢 ВОССТАНОВЛЕНИЕ @ {row['time']} (+{int(row['elapsed'])}s) | длительность деградации: {duration_deg:.0f}s")

    if in_degradation:
        print(f"⚠️  Деградация продолжается до конца теста!")

    # Итоговая сводка
    total_reqs = sum(r["rps"] for r in rows)
    all_lats = [r["avg_ms"] for r in rows if r["avg_ms"] > 0]
    p95_overall = percentile(all_lats, 95)
    max_err = max((r["error_rate"] for r in rows), default=0)

    print("\n" + "=" * 70)
    print(f"ИТОГ: {len(degradation_events)} событий деградации")
    print(f"  Всего запросов:    {total_reqs:.0f}")
    print(f"  Baseline RPS:      {bl_rps:.1f} req/s")
    print(f"  p95 latency:       {p95_overall:.0f} ms")
    print(f"  Max error rate:    {max_err*100:.1f}%")
    print(f"  Длительность теста: {duration_s:.0f}s")

    if degradation_events:
        print("\nСобытия деградации:")
        for i, ev in enumerate(degradation_events, 1):
            print(f"  [{i}] +{ev['elapsed_s']}s | RPS={ev['rps']} | Lat={ev['latency_ms']}ms | Err={ev['error_pct']}% | {'; '.join(ev['reasons'])}")

    # CSV export
    if args.csv:
        import csv
        with open(args.csv, "w", newline="") as cf:
            writer = csv.DictWriter(cf, fieldnames=["epoch","time","elapsed","rps","p50","p95","avg_ms","error_rate"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[*] CSV → {args.csv}")


if __name__ == "__main__":
    args = parse_args()
    analyze(args)
