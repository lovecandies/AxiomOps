import json
import logging
import time

from rocketmq import ClientConfiguration, Credentials, FilterExpression, SimpleConsumer

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.repository import (
    INVESTIGATION_REQUESTED,
    IncidentRepository,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def consume_forever() -> None:
    settings = ControlPlaneSettings()
    repository = IncidentRepository(Database(settings))

    while True:
        consumer: SimpleConsumer | None = None
        try:
            configuration = ClientConfiguration(
                settings.rocketmq_endpoints,
                Credentials(),
            )
            consumer = SimpleConsumer(
                configuration,
                settings.rocketmq_consumer_group,
                subscription={settings.rocketmq_topic: FilterExpression()},
                await_duration=5,
            )
            consumer.startup()
            while True:
                messages = consumer.receive(16, 30)
                for message in messages:
                    envelope = json.loads(message.body.decode("utf-8"))
                    if envelope["event_type"] != INVESTIGATION_REQUESTED:
                        raise ValueError(f"unsupported event: {envelope['event_type']}")
                    applied = repository.consume_investigation_requested(
                        settings.rocketmq_consumer_group,
                        envelope["event_id"],
                        envelope["incident_id"],
                        message.message_id,
                    )
                    consumer.ack(message)
                    logger.info(
                        "consumed event %s applied=%s",
                        envelope["event_id"],
                        applied,
                    )
        except Exception:
            logger.exception("consumer loop failed")
            time.sleep(2)
        finally:
            if consumer is not None:
                try:
                    consumer.shutdown()
                except Exception:
                    pass


if __name__ == "__main__":
    consume_forever()
