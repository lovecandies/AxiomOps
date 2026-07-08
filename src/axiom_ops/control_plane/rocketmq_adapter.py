import json
from typing import Any

from rocketmq import ClientConfiguration, Credentials, Message, Producer


class RocketMQPublisher:
    def __init__(self, endpoints: str, topic: str) -> None:
        self.topic = topic
        configuration = ClientConfiguration(endpoints, Credentials())
        self.producer = Producer(configuration, topics=[topic])

    def start(self) -> None:
        self.producer.startup()

    def publish(self, event: dict[str, Any]) -> str:
        message = Message()
        message.topic = self.topic
        message.tag = event["event_type"]
        message.keys = event["event_id"]
        message.body = json.dumps(event, ensure_ascii=False).encode("utf-8")
        receipt = self.producer.send(message)
        return receipt.message_id

    def close(self) -> None:
        self.producer.shutdown()
