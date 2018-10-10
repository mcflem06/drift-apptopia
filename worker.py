import os

import redis
from rq import Worker, Queue, Connection

listen = ['high', 'default', 'low']


r = redis.from_url("YOUR REDIS URI")
#r = redis.from_url(os.environ.get("REDIS_URL"))

if __name__ == '__main__':
    with Connection(r):
        worker = Worker(map(Queue, listen))
        worker.work()