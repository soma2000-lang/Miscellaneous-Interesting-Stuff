import mmh3
from bitarray import bitarray
import redis
from typing import List, Optional, Tuple
import logging
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor
import requests

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

class CDNCacheOptimizer:
    def __init__(self, redis_client: redis.Redis, capacity: int = 10000000, error_rate: float = 0.01):
        self.redis = redis_client
        self.bloom_filter = DistributedBloomFilter(redis_client, "cdn:cache:filter", capacity, error_rate)
        self.logger = logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=10)  # Adjust based on your needs
    
    def _generate_content_key(self, url: str, headers: dict) -> str:
        """Generate a unique key for the content based on URL and relevant headers."""
        relevant_headers = ['Accept', 'Accept-Encoding', 'Accept-Language']
        header_string = ''.join(f"{k}:{headers.get(k, '')}" for k in relevant_headers)
        return hashlib.md5(f"{url}{header_string}".encode()).hexdigest()
    
    def should_fetch_from_origin(self, url: str, headers: dict) -> bool:
        """Determine if content should be fetched from the origin server."""
        content_key = self._generate_content_key(url, headers)
        if not self.bloom_filter.contains(content_key):
            self.bloom_filter.add(content_key)
            return True
        return False
    
    def fetch_and_cache_content(self, url: str, headers: dict) -> Tuple[bytes, dict]:
        """Fetch content from origin and cache it."""
        try:
            response = requests.get(url, headers=headers)
            content = response.content
            response_headers = dict(response.headers)
            
            # Cache the content (in a real CDN, this would be more complex)
            content_key = self._generate_content_key(url, headers)
            self.redis.setex(f"cdn:content:{content_key}", 3600, content)  # Cache for 1 hour
            
            self.logger.info(f"Fetched and cached content for URL: {url}")
            return content, response_headers
        except Exception as e:
            self.logger.error(f"Error fetching content from origin: {str(e)}")
            raise
    
    def get_content(self, url: str, headers: dict) -> Tuple[bytes, dict]:
        """Get content, either from cache or origin."""
        content_key = self._generate_content_key(url, headers)
        cached_content = self.redis.get(f"cdn:content:{content_key}")
        
        if cached_content:
            self.logger.info(f"Cache hit for URL: {url}")
            return cached_content, {}  # In a real CDN, we'd also cache and return headers
        
        if self.should_fetch_from_origin(url, headers):
            self.logger.info(f"Fetching from origin for URL: {url}")
            return self.fetch_and_cache_content(url, headers)
        else:
            # This is a false positive. In a real CDN, we might have a secondary cache layer.
            self.logger.warning(f"Bloom filter false positive for URL: {url}")
            return self.fetch_and_cache_content(url, headers)
    
    def prefetch_content(self, urls: List[str]) -> None:
        """Prefetch a list of URLs to warm up the cache."""
        def prefetch_url(url):
            try:
                self.get_content(url, {})
                self.logger.info(f"Prefetched content for URL: {url}")
            except Exception as e:
                self.logger.error(f"Error prefetching content for URL {url}: {str(e)}")
        
        self.executor.map(prefetch_url, urls)
    
    def clear_cache_for_url(self, url: str) -> None:
        """Clear the cache for a specific URL (e.g., after content update)."""
        content_key = self._generate_content_key(url, {})
        self.redis.delete(f"cdn:content:{content_key}")
        # Note: We can't remove from Bloom filter, so it will remain as a potential false positive
        self.logger.info(f"Cleared cache for URL: {url}")

def simulate_cdn_requests():
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    cdn_optimizer = CDNCacheOptimizer(redis_client)
    
    # Simulate some requests
    urls = [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/image1.jpg",
        "https://example.com/page1",  # Repeated request
        "https://example.com/page3"
    ]
    
    for url in urls:
        start_time = time.time()
        content, headers = cdn_optimizer.get_content(url, {})
        end_time = time.time()
        
        print(f"URL: {url}")
        print(f"Content size: {len(content)} bytes")
        print(f"Request time: {end_time - start_time:.4f} seconds")
        print()
    
    # Simulate prefetching
    prefetch_urls = ["https://example.com/page4", "https://example.com/page5"]
    cdn_optimizer.prefetch_content(prefetch_urls)
    
    # Simulate cache clearing
    cdn_optimizer.clear_cache_for_url("https://example.com/page1")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    simulate_cdn_requests()

