from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.redis import RedisSaver


@contextmanager
def redis_checkpointer(redis_url: str) -> Iterator[RedisSaver]:
    with RedisSaver.from_conn_string(redis_url) as saver:
        saver.setup()
        yield saver
