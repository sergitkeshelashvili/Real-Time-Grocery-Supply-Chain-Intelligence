import os, random, time
from src.simulator.generators import generate_event
from src.streaming.producer import EventProducer
from src.common.logging import get_logger
from src.simulator.weather import fetch_weather_events

def main():
    rng = random.Random(int(os.getenv("RANDOM_SEED", "42")))
    rate = max(.1, float(os.getenv("EVENT_RATE", "5")))
    speed = max(.01, float(os.getenv("SIMULATION_SPEED", "1")))
    producer, log = EventProducer(), get_logger("simulator")
    weather_interval = max(300, int(os.getenv("WEATHER_POLL_SECONDS", "900")))
    next_weather_poll = 0
    try:
        while True:
            if time.time() >= next_weather_poll:
                try:
                    for weather_event in fetch_weather_events():
                        producer.send("weather", weather_event["payload"]["city"], weather_event)
                    if os.getenv("OPENWEATHER_API_KEY", "").strip():
                        log.info("weather snapshots published", extra={"event":"weather_snapshots_published"})
                    next_weather_poll = time.time() + weather_interval
                except RuntimeError as exc:
                    log.warning("Weather provider temporarily unavailable: %s", exc, extra={"event":"weather_fetch_failed"})
                    next_weather_poll = time.time() + weather_interval
            topic, key, event = generate_event(rng)
            producer.send(topic, key, event)
            log.info("produced %s", topic, extra={"event": "event_produced"})
            time.sleep(1.0 / rate)
    except KeyboardInterrupt: pass
    finally: producer.close()
if __name__ == "__main__": main()
