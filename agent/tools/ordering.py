"""Ordering service tools (read and place-order workflow)."""

from __future__ import annotations

from typing import Any

from agent.tools import http_client
from agent.tools.registry import ToolSpec, object_schema, register_tool


def _get_order(args: dict[str, Any]) -> dict[str, Any]:
    order_id = int(args["order_id"])
    status, body = http_client.get_json(
        http_client.ordering_base_url(),
        f"/orders/{order_id}",
    )
    return http_client.normalize_http_result(status, body, tool="get_order")


def _list_orders(args: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if "skip" in args:
        params["skip"] = int(args["skip"])
    if "limit" in args:
        params["limit"] = int(args["limit"])
    status, body = http_client.get_json(
        http_client.ordering_base_url(),
        "/orders",
        params=params or None,
    )
    return http_client.normalize_http_result(status, body, tool="list_orders")


def _list_order_statuses(args: dict[str, Any]) -> dict[str, Any]:
    _ = args
    status, body = http_client.get_json(
        http_client.ordering_base_url(),
        "/order-statuses",
    )
    return http_client.normalize_http_result(status, body, tool="list_order_statuses")


def _get_courier(args: dict[str, Any]) -> dict[str, Any]:
    courier_id = int(args["courier_id"])
    status, body = http_client.get_json(
        http_client.ordering_base_url(),
        f"/couriers/{courier_id}",
    )
    return http_client.normalize_http_result(status, body, tool="get_courier")


def _list_couriers(args: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if "skip" in args:
        params["skip"] = int(args["skip"])
    if "limit" in args:
        params["limit"] = int(args["limit"])
    status, body = http_client.get_json(
        http_client.ordering_base_url(),
        "/couriers",
        params=params or None,
    )
    return http_client.normalize_http_result(status, body, tool="list_couriers")


def _get_customer(args: dict[str, Any]) -> dict[str, Any]:
    customer_id = int(args["customer_id"])
    status, body = http_client.get_json(
        http_client.ordering_base_url(),
        f"/customers/{customer_id}",
    )
    return http_client.normalize_http_result(status, body, tool="get_customer")


def _get_food_place(args: dict[str, Any]) -> dict[str, Any]:
    food_place_id = int(args["food_place_id"])
    status, body = http_client.get_json(
        http_client.ordering_base_url(),
        f"/food-places/{food_place_id}",
    )
    return http_client.normalize_http_result(status, body, tool="get_food_place")


def _place_order(args: dict[str, Any]) -> dict[str, Any]:
    customer_id = int(args["customer_id"])
    food_place_id = int(args["food_place_id"])
    order_status_id = int(args.get("order_status_id", 1))
    payload = {
        "customer_id": customer_id,
        "food_place_id": food_place_id,
        "order_status_id": order_status_id,
    }
    status, body = http_client.post_json(
        http_client.ordering_base_url(),
        "/place-order",
        body=payload,
    )
    result = http_client.normalize_http_result(status, body, tool="place_order")
    if result.get("ok"):
        data = dict(body) if isinstance(body, dict) else {}
        data.setdefault("customer_id", customer_id)
        data.setdefault("food_place_id", food_place_id)
        data.setdefault("order_status_id", order_status_id)
        result["data"] = data
    return result


def register_ordering_tools() -> None:
    register_tool(
        ToolSpec(
            name="get_order",
            description="Get current order record including status label, courier, and route_status.",
            input_schema=object_schema(
                {"order_id": {"type": "integer", "description": "Order ID"}},
                required=["order_id"],
            ),
            handler=_get_order,
            service="ordering",
            status="stable",
            endpoint_ref="GET /orders/{order_id}",
        )
    )
    register_tool(
        ToolSpec(
            name="list_orders",
            description="List orders with pagination (skip, limit).",
            input_schema=object_schema(
                {
                    "skip": {"type": "integer", "description": "Offset (default 0)"},
                    "limit": {
                        "type": "integer",
                        "description": "Page size (default 50, max 200)",
                    },
                }
            ),
            handler=_list_orders,
            service="ordering",
            status="stable",
            endpoint_ref="GET /orders",
        )
    )
    register_tool(
        ToolSpec(
            name="list_order_statuses",
            description="List all order status IDs and human-readable labels.",
            input_schema=object_schema({}),
            handler=_list_order_statuses,
            service="ordering",
            status="stable",
            endpoint_ref="GET /order-statuses",
        )
    )
    register_tool(
        ToolSpec(
            name="get_courier",
            description="Get courier profile by ID.",
            input_schema=object_schema(
                {"courier_id": {"type": "integer", "description": "Courier ID"}},
                required=["courier_id"],
            ),
            handler=_get_courier,
            service="ordering",
            status="beta",
            endpoint_ref="GET /couriers/{courier_id}",
        )
    )
    register_tool(
        ToolSpec(
            name="list_couriers",
            description="List couriers with pagination.",
            input_schema=object_schema(
                {
                    "skip": {"type": "integer"},
                    "limit": {"type": "integer"},
                }
            ),
            handler=_list_couriers,
            service="ordering",
            status="beta",
            endpoint_ref="GET /couriers",
        )
    )
    register_tool(
        ToolSpec(
            name="get_customer",
            description="Get customer profile by ID.",
            input_schema=object_schema(
                {"customer_id": {"type": "integer"}},
                required=["customer_id"],
            ),
            handler=_get_customer,
            service="ordering",
            status="beta",
            endpoint_ref="GET /customers/{customer_id}",
        )
    )
    register_tool(
        ToolSpec(
            name="get_food_place",
            description="Get restaurant/food place by ID.",
            input_schema=object_schema(
                {"food_place_id": {"type": "integer"}},
                required=["food_place_id"],
            ),
            handler=_get_food_place,
            service="ordering",
            status="beta",
            endpoint_ref="GET /food-places/{food_place_id}",
        )
    )
    register_tool(
        ToolSpec(
            name="place_order",
            description=(
                "Place a new order for a customer at a food place. "
                "Queues route calculation and returns order_id, customer_id, food_place_id, "
                "order_status_id, and optional predicted_delivery_seconds."
            ),
            input_schema=object_schema(
                {
                    "customer_id": {"type": "integer", "description": "Customer placing the order"},
                    "food_place_id": {
                        "type": "integer",
                        "description": "Restaurant / food place ID",
                    },
                    "order_status_id": {
                        "type": "integer",
                        "description": "Initial status (1=CONFIRMED, default 1; must be 1–3)",
                    },
                },
                required=["customer_id", "food_place_id"],
            ),
            handler=_place_order,
            service="ordering",
            status="beta",
            endpoint_ref="POST /place-order",
        )
    )
