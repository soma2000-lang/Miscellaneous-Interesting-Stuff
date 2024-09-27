import math
import mmh3
from bitarray import bitarray
import pickle
import redis
from typing import Any, List, Optional
import logging

class BloomFilter:
    def __init__(self, capacity: int, error_rate: float = 0.01):
        """
        Initialize a Bloom Filter.
        
        :param capacity: The expected number of items to be added
        :param error_rate: The desired false positive probability
        """
        self.capacity = capacity
        self.error_rate = error_rate
        self.bit_size = self._get_size(capacity, error_rate)
        self.hash_count = self._get_hash_count(self.bit_size, capacity)
        self.bit_array = bitarray(self.bit_size)
        self.bit_array.setall(0)
    
    @staticmethod
    def _get_size(n: int, p: float) -> int:
        """Calculate the bit size of the Bloom filter."""
        m = -(n * math.log(p)) / (math.log(2)**2)
        return int(m)
    
    @staticmethod
    def _get_hash_count(m: int, n: int) -> int:
        """Calculate the number of hash functions to use."""
        k = (m / n) * math.log(2)
        return int(k)
    
    def add(self, item: Any) -> None:
        """Add an item to the Bloom filter."""
        for i in range(self.hash_count):
            index = mmh3.hash(str(item), i) % self.bit_size
            self.bit_array[index] = 1
    
    def contains(self, item: Any) -> bool:
        """Check if an item is in the Bloom filter."""
        for i in range(self.hash_count):
            index = mmh3.hash(str(item), i) % self.bit_size
            if not self.bit_array[index]:
                return False
        return True
    
    def __len__(self) -> int:
        """Return the number of bits set to 1."""
        return self.bit_array.count(1)

class DistributedBloomFilter:
    def __init__(self, redis_host: str, redis_port: int, redis_db: int, 
                 capacity: int, error_rate: float = 0.01, 
                 key_prefix: str = 'bloom'):
        """
        Initialize a Distributed Bloom Filter using Redis.
        
        :param redis_host: Redis server host
        :param redis_port: Redis server port
        :param redis_db: Redis database number
        :param capacity: The expected number of items to be added
        :param error_rate: The desired false positive probability
        :param key_prefix: Prefix for Redis keys
        """
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
        self.capacity = capacity
        self.error_rate = error_rate
        self.key_prefix = key_prefix
        self.logger = logging.getLogger(__name__)
        
        # Create or load the Bloom filter
        bloom_key = f"{self.key_prefix}:filter"
        if not self.redis.exists(bloom_key):
            self.bloom_filter = BloomFilter(capacity, error_rate)
            self._save_to_redis()
        else:
            self._load_from_redis()
    
    def add(self, item: Any) -> None:
        """Add an item to the Distributed Bloom Filter."""
        self.bloom_filter.add(item)
        self._save_to_redis()
    
    def contains(self, item: Any) -> bool:
        """Check if an item is in the Distributed Bloom Filter."""
        return self.bloom_filter.contains(item)
    
    def _save_to_redis(self) -> None:
        """Save the Bloom filter to Redis."""
        bloom_key = f"{self.key_prefix}:filter"
        try:
            self.redis.set(bloom_key, pickle.dumps(self.bloom_filter))
        except Exception as e:
            self.logger.error(f"Failed to save Bloom filter to Redis: {str(e)}")
    
    def _load_from_redis(self) -> None:
        """Load the Bloom filter from Redis."""
        bloom_key = f"{self.key_prefix}:filter"
        try:
            bloom_data = self.redis.get(bloom_key)
            if bloom_data:
                self.bloom_filter = pickle.loads(bloom_data)
            else:
                raise ValueError("Bloom filter data not found in Redis")
        except Exception as e:
            self.logger.error(f"Failed to load Bloom filter from Redis: {str(e)}")
            # Fallback to creating a new Bloom filter
            self.bloom_filter = BloomFilter(self.capacity, self.error_rate)
    
    def __len__(self) -> int:
        """Return the number of bits set to 1."""
        return len(self.bloom_filter)

class BloomFilterCache:
    def __init__(self, redis_host: str, redis_port: int, redis_db: int, 
                 capacity: int, error_rate: float = 0.01):
        """
        Initialize a Bloom Filter Cache for reducing disk lookups.
        
        :param redis_host: Redis server host
        :param redis_port: Redis server port
        :param redis_db: Redis database number
        :param capacity: The expected number of items to be added
        :param error_rate: The desired false positive probability
        """
        self.bloom_filter = DistributedBloomFilter(redis_host, redis_port, redis_db, 
                                                   capacity, error_rate)
        self.logger = logging.getLogger(__name__)
    
    def add_keys(self, keys: List[str]) -> None:
        """Add a list of keys to the Bloom filter cache."""
        for key in keys:
            self.bloom_filter.add(key)
    
    def might_exist(self, key: str) -> bool:
        """
        Check if a key might exist in the database.
        
        :param key: The key to check
        :return: True if the key might exist, False if it definitely doesn't exist
        """
        return self.bloom_filter.contains(key)
    
    def lookup(self, key: str, db_lookup_func: callable) -> Optional[Any]:
        """
        Perform a lookup using the Bloom filter cache.
        
        :param key: The key to look up
        :param db_lookup_func: Function to perform the actual database lookup
        :return: The value if found, None if not found
        """
        if not self.might_exist(key):
            return None
        
        try:
            value = db_lookup_func(key)
            if value is not None:
                return value
            else:
                self.logger.warning(f"False positive for key: {key}")
                return None
        except Exception as e:
            self.logger.error(f"Error during database lookup for key {key}: {str(e)}")
            return None

# Example usage
if __name__ == "__main__":
    import time
    
    # Simulated database
    database = {
        "user:1001": "John Doe",
        "user:1002": "Jane Smith",
        "user:1003": "Bob Johnson"
    }
    
    def db_lookup(key):
        # Simulate a slow database lookup
        time.sleep(0.1)
        return database.get(key)
    
    # Initialize the Bloom Filter Cache
    cache = BloomFilterCache("localhost", 6379, 0, capacity=1000, error_rate=0.01)
    
    # Add existing keys to the cache
    cache.add_keys(database.keys())
    
    # Perform lookups
    start_time = time.time()
    print(cache.lookup("user:1001", db_lookup))  # Should find
    print(cache.lookup("user:1004", db_lookup))  # Should not find, fast response
    print(cache.lookup("user:1002", db_lookup))  # Should find
    end_time = time.time()
    
    print(f"Total lookup time: {end_time - start_time:.4f} seconds")

