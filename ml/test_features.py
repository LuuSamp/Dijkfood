"""Unit tests for ml.features."""

from __future__ import annotations

import pandas as pd

from ml.features import delivery_features, demand_features, haversine_m, normalize_events


def test_normalize_and_delivery_features():
    rows = [
        {
            "type": "order_status",
            "order_id": 1,
            "status_id": 1,
            "timestamp": "2026-01-01T10:00:00+00:00",
            "food_place_id": 3,
            "customer_id": 10,
        },
        {
            "type": "order_status",
            "order_id": 1,
            "status_id": 6,
            "timestamp": "2026-01-01T10:30:00+00:00",
            "food_place_id": 3,
            "customer_id": 10,
        },
    ]
    events = normalize_events(rows)
    delivery = delivery_features(events)
    assert len(delivery) == 1
    assert delivery.iloc[0]["delivery_seconds"] == 1800.0
    assert "distance_m" in delivery.columns
    assert delivery.iloc[0]["distance_m"] == 0.0


def test_delivery_features_distance_enrichment():
    rows = [
        {
            "type": "order_status",
            "order_id": 42,
            "status_id": 1,
            "timestamp": "2026-01-01T12:00:00+00:00",
            "food_place_id": 1,
            "customer_id": 2,
        },
        {
            "type": "order_status",
            "order_id": 42,
            "status_id": 6,
            "timestamp": "2026-01-01T12:20:00+00:00",
            "food_place_id": 1,
            "customer_id": 2,
        },
    ]
    events = normalize_events(rows)
    delivery = delivery_features(
        events,
        route_distances={42: 2500.0},
        food_place_locations={1: (-23.55, -46.63)},
        customer_locations={2: (-23.56, -46.64)},
    )
    assert len(delivery) == 1
    assert delivery.iloc[0]["distance_m"] == 2500.0


def test_haversine_fallback_when_no_route():
    rows = [
        {
            "type": "order_status",
            "order_id": 7,
            "status_id": 1,
            "timestamp": "2026-01-01T08:00:00+00:00",
            "food_place_id": 1,
            "customer_id": 2,
        },
        {
            "type": "order_status",
            "order_id": 7,
            "status_id": 6,
            "timestamp": "2026-01-01T08:15:00+00:00",
            "food_place_id": 1,
            "customer_id": 2,
        },
    ]
    events = normalize_events(rows)
    fp = (-23.5505, -46.6333)
    cust = (-23.5600, -46.6400)
    delivery = delivery_features(
        events,
        food_place_locations={1: fp},
        customer_locations={2: cust},
    )
    expected = haversine_m(fp[0], fp[1], cust[0], cust[1])
    assert abs(delivery.iloc[0]["distance_m"] - expected) < 1.0


def test_demand_features():
    rows = [
        {
            "type": "order_status",
            "order_id": i,
            "status_id": 1,
            "timestamp": f"2026-01-01T{10 + (i % 3)}:00:00+00:00",
            "food_place_id": 1,
        }
        for i in range(5)
    ]
    events = normalize_events(rows)
    demand = demand_features(events)
    assert not demand.empty
    assert "order_count" in demand.columns
