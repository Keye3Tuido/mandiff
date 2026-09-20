QUEUE = []


def schedule(callback, key):
    QUEUE.append((callback, key))


def tick():
    if QUEUE:
        callback, key = QUEUE.pop(0)
        callback(key)
