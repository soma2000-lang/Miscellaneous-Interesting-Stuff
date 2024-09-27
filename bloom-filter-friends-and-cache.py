import mmh3
from bitarray import bitarray
import redis
from typing import List, Set, Tuple, Optional
import logging
import time
import json

class BloomFilter:
    def __init__(self, capacity: int, error_rate: float = 0.01):
        self.capacity = capacity
        self.error_rate = error_rate
        self.bit_size = self._get_size(capacity, error_rate)
        self.hash_count = self._get_hash_count(self.bit_size, capacity)
        self.bit_array = bitarray(self.bit_size)
        self.bit_array.setall(0)
    
    @staticmethod
    def _get_size(n: int, p: float) -> int:
        m = -(n * math.log(p)) / (math.log(2)**2)
        return int(m)
    
    @staticmethod
    def _get_hash_count(m: int, n: int) -> int:
        k = (m / n) * math.log(2)
        return int(k)
    
    def add(self, item: str) -> None:
        for i in range(self.hash_count):
            index = mmh3.hash(item, i) % self.bit_size
            self.bit_array[index] = 1
    
    def contains(self, item: str) -> bool:
        for i in range(self.hash_count):
            index = mmh3.hash(item, i) % self.bit_size
            if not self.bit_array[index]:
                return False
        return True

class DistributedBloomFilter:
    def __init__(self, redis_client: redis.Redis, key: str, capacity: int, error_rate: float = 0.01):
        self.redis = redis_client
        self.key = key
        self.bloom_filter = BloomFilter(capacity, error_rate)
        self._load_or_initialize()
    
    def _load_or_initialize(self) -> None:
        bloom_data = self.redis.get(self.key)
        if bloom_data:
            self.bloom_filter.bit_array = bitarray()
            self.bloom_filter.bit_array.frombytes(bloom_data)
        else:
            self._save_to_redis()
    
    def _save_to_redis(self) -> None:
        self.redis.set(self.key, self.bloom_filter.bit_array.tobytes())
    
    def add(self, item: str) -> None:
        self.bloom_filter.add(item)
        self._save_to_redis()
    
    def contains(self, item: str) -> bool:
        return self.bloom_filter.contains(item)

class FriendSuggestionSystem:
    def __init__(self, redis_client: redis.Redis, capacity: int = 1000000, error_rate: float = 0.01):
        self.redis = redis_client
        self.capacity = capacity
        self.error_rate = error_rate
        self.logger = logging.getLogger(__name__)
    
    def get_user_filter(self, user_id: str) -> DistributedBloomFilter:
        return DistributedBloomFilter(self.redis, f"user:{user_id}:friends", self.capacity, self.error_rate)
    
    def add_friend(self, user_id: str, friend_id: str) -> None:
        user_filter = self.get_user_filter(user_id)
        user_filter.add(friend_id)
        self.logger.info(f"Added friend {friend_id} to user {user_id}")
    
    def might_have_common_friends(self, user1_id: str, user2_id: str) -> bool:
        user1_filter = self.get_user_filter(user1_id)
        user2_filter = self.get_user_filter(user2_id)
        
        # Check if any of user1's friends might be in user2's filter
        for i in range(user1_filter.bloom_filter.bit_size):
            if user1_filter.bloom_filter.bit_array[i] and user2_filter.bloom_filter.bit_array[i]:
                return True
        return False
    
    def suggest_friends(self, user_id: str, potential_friends: List[str]) -> List[str]:
        user_filter = self.get_user_filter(user_id)
        suggestions = [
            friend for friend in potential_friends
            if self.might_have_common_friends(user_id, friend) and not user_filter.contains(friend)
        ]
        self.logger.info(f"Suggested {len(suggestions)} friends for user {user_id}")
        return suggestions

class QueryCache:
    def __init__(self, redis_client: redis.Redis, capacity: int = 1000000, error_rate: float = 0.01, ttl: int = 3600):
        self.redis = redis_client
        self.bloom_filter = DistributedBloomFilter(redis_client, "query_cache:filter", capacity, error_rate)
        self.ttl = ttl
        self.logger = logging.getLogger(__name__)
    
    def should_cache(self, query: str) -> bool:
        if not self.bloom_filter.contains(query):
            self.bloom_filter.add(query)
            return True
        return False
    
    def get(self, query: str) -> Optional[str]:
        if self.should_cache(query):
            return None
        
        result = self.redis.get(f"query_cache:{query}")
        if result:
            self.logger.info(f"Cache hit for query: {query}")
            return result.decode('utf-8')
        self.logger.info(f"Cache miss for query: {query}")
        return None
    
    def set(self, query: str, result: str) -> None:
        if self.should_cache(query):
            self.redis.setex(f"query_cache:{query}", self.ttl, result)
            self.logger.info(f"Cached result for query: {query}")

def simulate_friend_suggestions():
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    friend_system = FriendSuggestionSystem(redis_client)
    
    # Simulate adding friends
    friend_system.add_friend("user1", "friend1")
    friend_system.add_friend("user1", "friend2")
    friend_system.add_friend("user2", "friend2")
    friend_system.add_friend("user2", "friend3")
    
    # Suggest friends
    potential_friends = ["user2", "user3", "user4"]
    suggestions = friend_system.suggest_friends("user1", potential_friends)
    print(f"Friend suggestions for user1: {suggestions}")

def simulate_query_caching():
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    query_cache = QueryCache(redis_client)
    
    # Simulate query execution and caching
    def execute_query(query: str) -> str:
        # Simulate a slow database query
        time.sleep(1)
        return json.dumps({"result": f"Result for {query}"})
    
    queries = ["SELECT * FROM users", "SELECT * FROM products", "SELECT * FROM users"]
    
    for query in queries:
        start_time = time.time()
        result = query_cache.get(query)
        if result is None:
            result = execute_query(query)
            query_cache.set(query, result)
        execution_time = time.time() - start_time
        print(f"Query: {query}")
        print(f"Result: {result}")
        print(f"Execution time: {execution_time:.2f} seconds")
        print()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Simulating friend suggestions:")
    simulate_friend_suggestions()
    
    print("\nSimulating query caching:")
    simulate_query_caching()

