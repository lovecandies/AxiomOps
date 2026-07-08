import logging
import time
from uuid import uuid4

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.repository import IncidentRepository
from axiom_ops.control_plane.rocketmq_adapter import RocketMQPublisher


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run() -> None:
    settings = ControlPlaneSettings()
    repository = IncidentRepository(Database(settings))
    worker_id = f"relay-{uuid4().hex[:8]}"
    publisher: RocketMQPublisher | None = None

    while True:
        try:
            if publisher is None:
                publisher = RocketMQPublisher(
                    settings.rocketmq_endpoints,
                    settings.rocketmq_topic,
                )
                publisher.start()
            events = repository.claim_outbox(
                worker_id,
                settings.relay_lease_seconds,
            )
            if not events:
                time.sleep(settings.relay_poll_seconds)
                continue
            for event in events:
                try:
                    broker_message_id = publisher.publish(event.payload)
                    repository.mark_published(event.id, worker_id, broker_message_id)
                    logger.info("published outbox event %s", event.id)
                except Exception as exc:
                    repository.mark_failed(
                        event.id,
                        worker_id,
                        f"{type(exc).__name__}: {exc}",
                        retry_seconds=2,
                    )
                    logger.exception("failed to publish outbox event %s", event.id)
                    try:
                        publisher.close()
                    except Exception:
                        pass
                    publisher = None
                    break
        except Exception:
            logger.exception("outbox relay loop failed")
            publisher = None
            time.sleep(2)


if __name__ == "__main__":
    run()
