import time

class LeakyBucket:
    def __init__(self, capacity, rate):
        self.capacity = capacity  # capacity of bucket
        self.rate = rate  # date rate
        self.tokens = 0  # tokens size in bucket
        self.last_time = time.time()  # last update time

    def _update_tokens(self):
        now = time.time()
        elapsed_time = now - self.last_time
        self.tokens = min(self.capacity, self.tokens + elapsed_time * self.rate)
        self.last_time = now

    def allow_request(self, tokens_requested):
        self._update_tokens()
        if self.tokens >= tokens_requested:
            self.tokens -= tokens_requested
            return True
        return False


bucket = LeakyBucket(capacity=40, rate=1)


for _ in range(55):
    if bucket.allow_request(1):
        print("Request allowed.")
    else:
        print("Request denied. Wait for a moment.")
        time.sleep(1)
