from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import time
import random
import heapq
from dataclasses import dataclass
from collections import defaultdict
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Server:
    """Represents a backend server instance"""
    id: str
    host: str
    port: int
    weight: float = 1.0
    current_connections: int = 0
    cpu_utilization: float = 0.0
    response_time: float = 0.0
    is_healthy: bool = True
    last_health_check: float = time.time()

class LoadBalancerException(Exception):
    """Base exception for load balancer errors"""
    pass

class ServerUnavailableException(LoadBalancerException):
    """Raised when no servers are available to handle requests"""
    pass

class LoadBalancer(ABC):
    """Abstract base class for load balancer implementations"""
    
    def __init__(self, health_check_interval: int = 30):
        self.servers: Dict[str, Server] = {}
        self.health_check_interval = health_check_interval
        self._lock = threading.Lock()
        self._start_health_checker()

    def add_server(self, server: Server) -> None:
        """Add a server to the pool"""
        with self._lock:
            self.servers[server.id] = server
            logger.info(f"Added server {server.id} to the pool")

    def remove_server(self, server_id: str) -> None:
        """Remove a server from the pool"""
        with self._lock:
            if server_id in self.servers:
                del self.servers[server_id]
                logger.info(f"Removed server {server_id} from the pool")

    def _start_health_checker(self) -> None:
        """Start the background health checking thread"""
        def health_check_loop():
            while True:
                self._check_servers_health()
                time.sleep(self.health_check_interval)
        
        thread = threading.Thread(target=health_check_loop, daemon=True)
        thread.start()

    def _check_servers_health(self) -> None:
        """Perform health checks on all servers"""
        with self._lock:
            current_time = time.time()
            for server in self.servers.values():
                try:
                    # Simulate health check - in production, replace with actual health check logic
                    is_healthy = self._perform_health_check(server)
                    server.is_healthy = is_healthy
                    server.last_health_check = current_time
                except Exception as e:
                    logger.error(f"Health check failed for server {server.id}: {str(e)}")
                    server.is_healthy = False

    def _perform_health_check(self, server: Server) -> bool:
        """
        Perform actual health check on server
        Should be implemented with real health check logic in production
        """
        # Placeholder for actual health check implementation
        return True

    @abstractmethod
    def get_next_server(self) -> Server:
        """Get the next server based on the load balancing algorithm"""
        pass

    def _get_healthy_servers(self) -> List[Server]:
        """Return list of healthy servers"""
        healthy_servers = [s for s in self.servers.values() if s.is_healthy]
        if not healthy_servers:
            raise ServerUnavailableException("No healthy servers available")
        return healthy_servers

class RoundRobinLoadBalancer(LoadBalancer):
    """Round Robin load balancing implementation"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_index = 0
        
    def get_next_server(self) -> Server:
        """Get next server using round-robin algorithm"""
        with self._lock:
            healthy_servers = self._get_healthy_servers()
            self._current_index = (self._current_index + 1) % len(healthy_servers)
            return healthy_servers[self._current_index]

class WeightedRoundRobinLoadBalancer(LoadBalancer):
    """Weighted Round Robin load balancing implementation"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_weights: Dict[str, float] = {}
        
    def get_next_server(self) -> Server:
        """Get next server using weighted round-robin algorithm"""
        with self._lock:
            healthy_servers = self._get_healthy_servers()
            
            # Initialize or update current weights
            for server in healthy_servers:
                if server.id not in self._current_weights:
                    self._current_weights[server.id] = server.weight
            
            # Find server with maximum current weight
            max_weight_server = max(
                healthy_servers,
                key=lambda s: self._current_weights.get(s.id, 0)
            )
            
            # Update weights
            for server_id in self._current_weights:
                self._current_weights[server_id] -= max_weight_server.weight
            self._current_weights[max_weight_server.id] += sum(
                s.weight for s in healthy_servers
            )
            
            return max_weight_server

class LeastConnectionsLoadBalancer(LoadBalancer):
    """Least Connections load balancing implementation"""
    
    def get_next_server(self) -> Server:
        """Get server with least active connections"""
        with self._lock:
            healthy_servers = self._get_healthy_servers()
            return min(healthy_servers, key=lambda s: s.current_connections)

class WeightedLeastConnectionsLoadBalancer(LoadBalancer):
    """Weighted Least Connections load balancing implementation"""
    
    def get_next_server(self) -> Server:
        """Get server based on weighted least connections algorithm"""
        with self._lock:
            healthy_servers = self._get_healthy_servers()
            return min(
                healthy_servers,
                key=lambda s: s.current_connections / s.weight
            )

class IPHashLoadBalancer(LoadBalancer):
    """IP Hash based load balancing implementation"""
    
    def get_server_for_ip(self, ip_address: str) -> Server:
        """Get consistent server based on IP hash"""
        with self._lock:
            healthy_servers = self._get_healthy_servers()
            hash_value = hash(ip_address)
            index = hash_value % len(healthy_servers)
            return healthy_servers[index]

class LeastResponseTimeLoadBalancer(LoadBalancer):
    """Least Response Time load balancing implementation"""
    
    def get_next_server(self) -> Server:
        """Get server with lowest response time"""
        with self._lock:
            healthy_servers = self._get_healthy_servers()
            return min(healthy_servers, key=lambda s: s.response_time)

class ResourceBasedLoadBalancer(LoadBalancer):
    """Resource-based (CPU/Memory) load balancing implementation"""
    
    def get_next_server(self) -> Server:
        """Get server with lowest resource utilization"""
        with self._lock:
            healthy_servers = self._get_healthy_servers()
            return min(healthy_servers, key=lambda s: s.cpu_utilization)

# Example usage and testing
def test_load_balancers():
    # Create test servers
    servers = [
        Server("s1", "server1.example.com", 8001, weight=1),
        Server("s2", "server2.example.com", 8002, weight=2),
        Server("s3", "server3.example.com", 8003, weight=3)
    ]
    
    # Test Round Robin
    rr_lb = RoundRobinLoadBalancer()
    for server in servers:
        rr_lb.add_server(server)
    
    # Test the round robin distribution
    selected_servers = [rr_lb.get_next_server().id for _ in range(6)]
    print(f"Round Robin Distribution: {selected_servers}")
    
    # Test Weighted Round Robin
    wrr_lb = WeightedRoundRobinLoadBalancer()
    for server in servers:
        wrr_lb.add_server(server)
    
    # Test the weighted distribution
    selected_servers = [wrr_lb.get_next_server().id for _ in range(6)]
    print(f"Weighted Round Robin Distribution: {selected_servers}")

if __name__ == "__main__":
    test_load_balancers()
