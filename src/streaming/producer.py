import json, time
from confluent_kafka import Producer
from src.common.config import KAFKA
from src.common.logging import get_logger

log = get_logger("simulator")
class EventProducer:
    def __init__(self):
        self.producer = Producer({"bootstrap.servers": KAFKA, "client.id": "grocery-simulator", "enable.idempotence": True})
    def send(self, topic, key, event):
        while True:
            try:
                self.producer.produce(topic, key=key, value=json.dumps(event), callback=self._delivery)
                self.producer.poll(0)
                return
            except BufferError:
                self.producer.poll(1)
            except Exception as exc:
                log.warning("Kafka send retry: %s", exc); time.sleep(2)
    def _delivery(self, error, message):
        if error: log.error("Kafka delivery failed: %s", error)
    def close(self): self.producer.flush(10)
