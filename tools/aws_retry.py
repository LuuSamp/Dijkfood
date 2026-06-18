"""Shared AWS client retry settings and throttling-safe helpers."""

from __future__ import annotations

import time
from typing import Any

from botocore.config import Config
from botocore.exceptions import ClientError

# Use for boto3.client(...) in deploy and other control-plane scripts.
BOTO_RETRY_CONFIG = Config(
    retries={"max_attempts": 12, "mode": "adaptive"},
)

_DDB_THROTTLE_CODES = frozenset(
    {
        "ThrottlingException",
        "ProvisionedThroughputExceededException",
        "RequestLimitExceeded",
    }
)


def describe_dynamodb_table(ddb: Any, table_name: str) -> dict[str, Any]:
    """describe_table with exponential backoff on DynamoDB control-plane throttling."""
    last_exc: ClientError | None = None
    for attempt in range(10):
        try:
            return ddb.describe_table(TableName=table_name)["Table"]
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in _DDB_THROTTLE_CODES:
                raise
            last_exc = exc
            delay = min(30.0, 0.4 * (2**attempt))
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc
