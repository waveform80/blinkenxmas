import json
from queue import Empty
from threading import Thread, Event

import paho.mqtt.client as mqtt


class MessageThread(Thread):
    def __init__(self, queue, config):
        super().__init__(target=self.listen, daemon=True)
        self.queue = queue
        self.host = config.broker_address
        self.port = config.broker_port
        self.topic = config.topic
        self.exception = None
        self._stopping = Event()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc_info):
        if self.exception:
            raise self.exception
        self.stop()

    def stop(self):
        self._stopping.set()

    def listen(self):
        try:
            client = mqtt.Client(clean_session=True)
            client.connect(self.host, self.port, keepalive=120)
            while not self._stopping.wait(0):
                client.loop(timeout=0.1)
                try:
                    frames = self.queue.get(timeout=1)
                except Empty:
                    pass
                else:
                    client.publish(self.topic, json.dumps(frames), qos=1)
        except Exception as e:
            self.exception = e
