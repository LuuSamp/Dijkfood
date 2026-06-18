"""Build ML training datasets from S3 analytics events and upload to datalake."""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
import psycopg
from dotenv import load_dotenv

from ml.features import (
    anomaly_features,
    delivery_features,
    demand_features,
    normalize_events,
)

ROOT = Path(__file__).resolve().parent.parent
MIN_DELIVERY_ROWS = 20


def _load_env() -> None:
    load_dotenv(ROOT / ".env", override=False)
    if (ROOT / "connection.env").is_file():
        load_dotenv(ROOT / "connection.env", override=True)


def _read_events_s3(s3, bucket: str, prefix: str = "events/") -> pd.DataFrame:
    rows: list[dict] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            if not key.endswith(".jsonl"):
                continue
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
            for line in body.splitlines():
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return normalize_events(rows)


def _upload_csv(s3, bucket: str, key: str, df: pd.DataFrame) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue().encode("utf-8"))
    print(f"  uploaded s3://{bucket}/{key} ({len(df)} rows)")


def _db_conninfo() -> str:
    return (
        f"host={os.environ.get('DB_HOST', '')} "
        f"port={os.environ.get('DB_PORT', '5432')} "
        f"dbname={os.environ.get('DB_NAME', '')} "
        f"user={os.environ.get('DB_USER', '')} "
        f"password={os.environ.get('DB_PASSWORD', '')} "
        "connect_timeout=10"
    )


def _load_rds_locations() -> tuple[dict[int, tuple[float, float]], dict[int, tuple[float, float]]]:
    """customer_id / food_place_id -> (lat, lon) from RDS."""
    customers: dict[int, tuple[float, float]] = {}
    food_places: dict[int, tuple[float, float]] = {}
    if not os.environ.get("DB_HOST"):
        return customers, food_places
    try:
        with psycopg.connect(_db_conninfo()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT customer_id, lat, lon FROM customers")
                for row in cur.fetchall():
                    customers[int(row[0])] = (float(row[1]), float(row[2]))
                cur.execute("SELECT food_place_id, lat, lon FROM food_places")
                for row in cur.fetchall():
                    food_places[int(row[0])] = (float(row[1]), float(row[2]))
    except Exception as exc:
        print(f"  WARNING: could not load RDS locations for distance fallback: {exc}")
    return customers, food_places


def _load_route_distances(
    ddb,
    table_name: str,
) -> tuple[dict[int, float], dict[tuple[int, int], float]]:
    """Scan DynamoDB routes for order# and pair# distance_m values."""
    order_distances: dict[int, float] = {}
    pair_distances: dict[tuple[int, int], float] = {}
    if not table_name:
        return order_distances, pair_distances
    table = ddb.Table(table_name)
    last_key: dict[str, Any] | None = None
    while True:
        scan_kwargs: dict[str, Any] = {
            "ProjectionExpression": "routeKey, payload",
        }
        if last_key is not None:
            scan_kwargs["ExclusiveStartKey"] = last_key
        resp = table.scan(**scan_kwargs)
        for item in resp.get("Items", []):
            route_key = str(item.get("routeKey") or "")
            payload = item.get("payload") or {}
            distance_m = payload.get("distance_m")
            if distance_m is None:
                continue
            dist = float(distance_m)
            if route_key.startswith("order#"):
                try:
                    order_distances[int(route_key.split("#", 1)[1])] = dist
                except ValueError:
                    continue
            elif route_key.startswith("pair#"):
                parts = route_key.split("#")
                if len(parts) == 3:
                    try:
                        pair_distances[(int(parts[1]), int(parts[2]))] = dist
                    except ValueError:
                        continue
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
    return order_distances, pair_distances


def prepare_all(*, bucket: str | None = None) -> dict[str, int]:
    _load_env()
    bucket = bucket or os.environ.get("DATALAKE_S3_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError("Set DATALAKE_S3_BUCKET in connection.env")
    region = os.environ.get("AWS_REGION", "us-east-1")
    s3 = boto3.client("s3", region_name=region)
    events = _read_events_s3(s3, bucket)
    if events.empty:
        print("No events found in datalake; run load test first.")
        return {"delivery": 0, "demand": 0, "anomaly": 0}

    routes_table = (os.environ.get("DYNAMODB_ROUTES_TABLE") or "").strip()
    ddb = boto3.resource("dynamodb", region_name=region)
    order_distances, pair_distances = _load_route_distances(ddb, routes_table)
    customer_locations, food_place_locations = _load_rds_locations()
    if order_distances or pair_distances:
        print(
            f"  route distances: {len(order_distances)} orders, "
            f"{len(pair_distances)} pairs from DynamoDB"
        )

    delivery_df = delivery_features(
        events,
        route_distances=order_distances,
        pair_distances=pair_distances,
        customer_locations=customer_locations,
        food_place_locations=food_place_locations,
    )
    demand_df = demand_features(events)
    anomaly_df = anomaly_features(events)

    counts = {"delivery": len(delivery_df), "demand": len(demand_df), "anomaly": len(anomaly_df)}
    if not delivery_df.empty:
        _upload_csv(s3, bucket, "ml/datasets/delivery/train.csv", delivery_df)
    if not demand_df.empty:
        _upload_csv(s3, bucket, "ml/datasets/demand/train.csv", demand_df)
    if not anomaly_df.empty:
        _upload_csv(s3, bucket, "ml/datasets/anomaly/train.csv", anomaly_df)
    return counts


def main() -> None:
    p = argparse.ArgumentParser(description="Prepare ML datasets from analytics events")
    p.add_argument("--bucket", default="", help="Override DATALAKE_S3_BUCKET")
    args = p.parse_args()
    bucket = args.bucket.strip() or None
    counts = prepare_all(bucket=bucket)
    print("Dataset row counts:", counts)
    if counts["delivery"] < MIN_DELIVERY_ROWS:
        print(
            f"WARNING: fewer than {MIN_DELIVERY_ROWS} delivery rows; "
            "training will use heuristic fallback until more data is collected."
        )


if __name__ == "__main__":
    main()
