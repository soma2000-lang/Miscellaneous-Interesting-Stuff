import mmh3
from bitarray import bitarray
import redis
from typing import List, Tuple, Optional
import logging
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import requests
import hashlib
import struct

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
    
    def add(self, item: bytes) -> None:
        for i in range(self.hash_count):
            index = mmh3.hash(item, i) % self.bit_size
            self.bit_array[index] = 1
    
    def contains(self, item: bytes) -> bool:
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
    
    def add(self, item: bytes) -> None:
        self.bloom_filter.add(item)
        self._save_to_redis()
    
    def contains(self, item: bytes) -> bool:
        return self.bloom_filter.contains(item)

class SafeBrowsingChecker:
    def __init__(self, redis_client: redis.Redis, capacity: int = 100000000, error_rate: float = 0.000001):
        self.bloom_filter = DistributedBloomFilter(redis_client, "safe_browsing", capacity, error_rate)
        self.logger = logging.getLogger(__name__)
        self.redis = redis_client
    
    def canonicalize_url(self, url: str) -> str:
        """Canonicalize the URL to a standard format."""
        parsed = urllib.parse.urlparse(url.strip().lower())
        hostname = parsed.hostname or ""
        path = parsed.path or "/"
        query = parsed.query
        
        # Remove www. from the beginning of the hostname
        if hostname.startswith("www."):
            hostname = hostname[4:]
        
        # Ensure the path ends with a '/'
        if not path.endswith("/"):
            path += "/"
        
        # Sort query parameters
        if query:
            query_params = sorted(urllib.parse.parse_qsl(query))
            query = urllib.parse.urlencode(query_params)
        
        return urllib.parse.urlunparse((parsed.scheme, hostname, path, "", query, ""))
    
    def generate_url_variants(self, url: str) -> List[str]:
        """Generate URL variants to check against the Bloom filter."""
        canonical_url = self.canonicalize_url(url)
        parsed = urllib.parse.urlparse(canonical_url)
        
        variants = [
            canonical_url,
            f"{parsed.scheme}://{parsed.netloc}/",
            parsed.netloc,
        ]
        
        path_parts = parsed.path.split("/")
        for i in range(1, len(path_parts)):
            variants.append(f"{parsed.scheme}://{parsed.netloc}{'/'.join(path_parts[:i])}/")
        
        return variants
    
    def add_malicious_url(self, url: str) -> None:
        """Add a malicious URL to the Bloom filter."""
        variants = self.generate_url_variants(url)
        for variant in variants:
            self.bloom_filter.add(variant.encode())
        self.logger.info(f"Added malicious URL and its variants: {url}")
    
    def is_potentially_malicious(self, url: str) -> bool:
        """Check if a URL is potentially malicious."""
        variants = self.generate_url_variants(url)
        return any(self.bloom_filter.contains(variant.encode()) for variant in variants)
    
    def bulk_check_urls(self, urls: List[str]) -> List[bool]:
        """Check multiple URLs in parallel."""
        with ThreadPoolExecutor(max_workers=10) as executor:
            return list(executor.map(self.is_potentially_malicious, urls))

class SafeBrowsingSystem:
    def __init__(self, redis_client: redis.Redis, update_interval: int = 3600):
        self.safe_browsing = SafeBrowsingChecker(redis_client)
        self.logger = logging.getLogger(__name__)
        self.update_interval = update_interval
        self.last_update = 0
    
    def check_url(self, url: str) -> Tuple[bool, str]:
        """Check if a URL is safe to browse."""
        self._update_if_needed()
        is_malicious = self.safe_browsing.is_potentially_malicious(url)
        status = "potentially malicious" if is_malicious else "safe"
        return is_malicious, status
    
    def bulk_check_urls(self, urls: List[str]) -> List[Tuple[str, bool, str]]:
        """Check multiple URLs and return their status."""
        self._update_if_needed()
        results = self.safe_browsing.bulk_check_urls(urls)
        return [(url, is_malicious, "potentially malicious" if is_malicious else "safe") 
                for url, is_malicious in zip(urls, results)]
    
    def _update_if_needed(self) -> None:
        """Update the malicious URL database if the update interval has passed."""
        current_time = time.time()
        if current_time - self.last_update > self.update_interval:
            self._update_malicious_urls()
            self.last_update = current_time
    
    def _update_malicious_urls(self) -> None:
        """Update the malicious URL database."""
        # In a real implementation, this would fetch updates from a trusted source
        # For demonstration, we'll just add a few example URLs
        example_malicious_urls = [
            "http://malicious-example.com/phishing",
            "https://fake-bank.com/login",
            "http://malware-distribution.net/download"
        ]
        for url in example_malicious_urls:
            self.safe_browsing.add_malicious_url(url)
        self.logger.info("Updated malicious URL database")

def simulate_safe_browsing():
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    safe_browsing_system = SafeBrowsingSystem(redis_client)
    
    # Simulate checking various URLs
    urls_to_check = [
        "https://www.google.com",
        "http://malicious-example.com/phishing",
        "https://fake-bank.com/login/user123",
        "https://legitimate-site.com/products",
        "http://malware-distribution.net/download/file.exe"
    ]
    
    print("Individual URL Checks:")
    for url in urls_to_check:
        is_malicious, status = safe_browsing_system.check_url(url)
        print(f"URL: {url}")
        print(f"Status: {status}")
        print()
    
    print("Bulk URL Check:")
    bulk_results = safe_browsing_system.bulk_check_urls(urls_to_check)
    for url, is_malicious, status in bulk_results:
        print(f"URL: {url}")
        print(f"Status: {status}")
        print()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    simulate_safe_browsing()

