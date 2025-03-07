# Copyright 2023 Iguazio
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# flake8: noqa  - this is until we take care of the F401 violations with respect to __all__ & sphinx

__all__ = [
    "DataItem",
    "get_store_resource",
    "ParquetTarget",
    "CSVTarget",
    "NoSqlTarget",
    "StreamTarget",
    "KafkaTarget",
    "CSVSource",
    "ParquetSource",
    "BigQuerySource",
    "HttpSource",
    "StreamSource",
    "KafkaSource",
    "RedisStore",
    "DatabricksFileSystemDisableCache",
    "DatabricksFileBugFixed",
    "get_stream_pusher",
]

import fsspec

import mlrun.datastore.wasbfs
from mlrun.platforms.iguazio import (
    HTTPOutputStream,
    KafkaOutputStream,
    OutputStream,
    parse_path,
)

from ..utils import logger
from .base import DataItem
from .datastore import StoreManager, in_memory_store, uri_to_ipython
from .dbfs_store import DatabricksFileBugFixed, DatabricksFileSystemDisableCache
from .s3 import parse_s3_bucket_and_key
from .sources import (
    BigQuerySource,
    CSVSource,
    HttpSource,
    KafkaSource,
    ParquetSource,
    StreamSource,
)
from .store_resources import (
    get_store_resource,
    get_store_uri,
    is_store_uri,
    parse_store_uri,
)
from .targets import CSVTarget, NoSqlTarget, ParquetTarget, StreamTarget
from .utils import get_kafka_brokers_from_dict, parse_kafka_url

store_manager = StoreManager()

if hasattr(fsspec, "register_implementation"):
    fsspec.register_implementation(
        "dbfs", DatabricksFileSystemDisableCache, clobber=True
    )
else:
    from fsspec.registry import known_implementations

    known_implementations["dbfs"] = {
        "class": "mlrun.datastore.dbfs_store.DatabricksFileSystemDisableCache",
        "err": "Please make sure your fsspec version supports dbfs",
    }

    del known_implementations

del fsspec  # clear the module namespace


def set_in_memory_item(key, value):
    item = store_manager.object(f"memory://{key}")
    item.put(value)
    return item


def get_in_memory_items():
    return in_memory_store._items


def get_stream_pusher(stream_path: str, **kwargs):
    """get a stream pusher object from URL.

    common kwargs::

        create:             create a new stream if doesnt exist
        shards:             number of shards
        retention_in_hours: stream retention in hours

    :param stream_path:        path/url of stream
    """

    kafka_brokers = get_kafka_brokers_from_dict(kwargs)
    if stream_path.startswith("kafka://") or kafka_brokers:
        topic, brokers = parse_kafka_url(stream_path, kafka_brokers)
        return KafkaOutputStream(topic, brokers, kwargs.get("kafka_producer_options"))
    elif stream_path.startswith("http://") or stream_path.startswith("https://"):
        return HTTPOutputStream(stream_path=stream_path)
    elif "://" not in stream_path:
        return OutputStream(stream_path, **kwargs)
    elif stream_path.startswith("v3io"):
        endpoint, stream_path = parse_path(stream_path)
        endpoint = kwargs.pop("endpoint", None) or endpoint
        return OutputStream(stream_path, endpoint=endpoint, **kwargs)
    elif stream_path.startswith("dummy://"):
        return _DummyStream(**kwargs)
    else:
        raise ValueError(f"unsupported stream path {stream_path}")


class _DummyStream:
    """stream emulator for tests and debug"""

    def __init__(self, event_list=None, **kwargs):
        self.event_list = event_list or []

    def push(self, data):
        if not isinstance(data, list):
            data = [data]
        for item in data:
            logger.info(f"dummy stream got event: {item}")
            self.event_list.append(item)
