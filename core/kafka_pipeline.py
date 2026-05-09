"""
Kafka Pipeline — transfers extension packages to the database layer.

PRIMARY:  Real Kafka broker via Docker Desktop (confluent-kafka-python).
FALLBACK: In-process asyncio queue when Docker/Kafka is not reachable.

Start Kafka:  docker compose up -d
Stop Kafka:   docker compose down

Topics used:
  module.store   — new module extension packages
  module.update  — capability/routing updates for existing modules
"""
import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional

from core.event_bus import Severity, bus

KAFKA_BOOTSTRAP = "localhost:9092"
TOPIC_STORE     = "module.store"
TOPIC_UPDATE    = "module.update"
GROUP_ID        = "csi-consumer-group"

# ── Kafka availability probe ───────────────────────────────────────────────

def _kafka_available() -> bool:
    """Quick TCP probe to see if Kafka broker is reachable."""
    import socket
    try:
        host, port = KAFKA_BOOTSTRAP.split(":")
        with socket.create_connection((host, int(port)), timeout=1.5):
            return True
    except Exception:
        return False


# ── Real Kafka producer/consumer ───────────────────────────────────────────

class _RealKafkaProducer:
    def __init__(self):
        from confluent_kafka import Producer
        self._p = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP,
                            "socket.timeout.ms": 3000})

    def produce(self, topic: str, key: str, value: dict):
        self._p.produce(
            topic,
            key=key.encode(),
            value=json.dumps(value, default=str).encode(),
        )
        self._p.poll(0)

    def flush(self):
        self._p.flush(timeout=5)


class _RealKafkaConsumer:
    def __init__(self, topics: List[str]):
        from confluent_kafka import Consumer
        self._c = Consumer({
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "group.id": GROUP_ID,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            "socket.timeout.ms": 3000,
        })
        self._c.subscribe(topics)

    def poll(self, timeout: float = 1.0):
        """Return (key, value_dict) or None."""
        msg = self._c.poll(timeout)
        if msg is None or msg.error():
            return None
        try:
            value = json.loads(msg.value().decode())
            key   = msg.key().decode() if msg.key() else ""
            return key, value
        except Exception:
            return None

    def close(self):
        self._c.close()


# ── Unified pipeline ───────────────────────────────────────────────────────

class KafkaPipeline:
    """
    Unified Kafka pipeline.
    Automatically uses real Kafka when Docker is running,
    falls back to in-process queue otherwise.
    """

    _instance: Optional["KafkaPipeline"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queue: Optional[asyncio.Queue] = None
            cls._instance._consumer_callback: Optional[Callable] = None
            cls._instance._running = False
            cls._instance._use_real_kafka = False
            cls._instance._producer: Optional[_RealKafkaProducer] = None
            cls._instance._consumer: Optional[_RealKafkaConsumer] = None
            cls._instance._loop: Optional[asyncio.AbstractEventLoop] = None
        return cls._instance

    def initialize(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._queue = asyncio.Queue()

        # Probe Kafka
        if _kafka_available():
            try:
                self._producer = _RealKafkaProducer()
                self._consumer = _RealKafkaConsumer([TOPIC_STORE, TOPIC_UPDATE])
                self._use_real_kafka = True
                bus.emit("KAFKA PIPELINE",
                         f"✅  Connected to Kafka broker at {KAFKA_BOOTSTRAP}",
                         Severity.SUCCESS)
            except Exception as e:
                self._use_real_kafka = False
                bus.emit("KAFKA PIPELINE",
                         f"⚠️   Kafka init failed ({e}), using in-process queue",
                         Severity.WARNING)
        else:
            self._use_real_kafka = False
            bus.emit("KAFKA PIPELINE",
                     "⚠️   Kafka broker not reachable — using in-process queue fallback",
                     Severity.WARNING)
            bus.emit("KAFKA PIPELINE",
                     "ℹ️   Start Docker Desktop and run: docker compose up -d")

    def set_consumer(self, callback: Callable):
        self._consumer_callback = callback

    @property
    def mode(self) -> str:
        return "kafka" if self._use_real_kafka else "in-process"

    # ── Produce ────────────────────────────────────────────────────────────

    async def produce(self, module_id: str, topic: str, payload: Dict[str, Any]):
        bus.emit("KAFKA PIPELINE",
                 f"🚀  [{self.mode}] Producing to '{topic}' for {module_id}",
                 module_id=module_id)

        message = {
            "topic":       topic,
            "module_id":   module_id,
            "payload":     payload,
            "produced_at": time.time(),
        }

        if self._use_real_kafka:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, self._producer.produce, topic, module_id, message
            )
            bus.emit("KAFKA PIPELINE",
                     f"📨  Message delivered to Kafka topic '{topic}'",
                     module_id=module_id)
        else:
            if self._queue:
                await self._queue.put(message)
            bus.emit("KAFKA PIPELINE",
                     f"📨  Message queued in-process on '{topic}'",
                     module_id=module_id)

    # ── Consume ────────────────────────────────────────────────────────────

    async def start_consuming(self):
        self._running = True
        if self._use_real_kafka:
            await self._consume_real()
        else:
            await self._consume_inprocess()

    async def _consume_real(self):
        """Poll real Kafka broker in a thread to avoid blocking the event loop."""
        bus.emit("KAFKA PIPELINE", "👂  Real Kafka consumer started")
        while self._running:
            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, self._consumer.poll, 1.0
                )
                if result and self._consumer_callback:
                    _, message = result
                    await self._consumer_callback(message)
            except Exception as e:
                bus.emit("KAFKA PIPELINE", f"❌  Consumer error: {e}", Severity.ERROR)
                await asyncio.sleep(1.0)

    async def _consume_inprocess(self):
        """Drain the in-process asyncio queue."""
        while self._running:
            try:
                if self._queue:
                    message = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                    if self._consumer_callback:
                        await self._consumer_callback(message)
                    self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                bus.emit("KAFKA PIPELINE", f"❌  Consumer error: {e}", Severity.ERROR)

    def stop(self):
        self._running = False
        if self._use_real_kafka and self._producer:
            try:
                self._producer.flush()
            except Exception:
                pass
        if self._use_real_kafka and self._consumer:
            try:
                self._consumer.close()
            except Exception:
                pass


pipeline = KafkaPipeline()
