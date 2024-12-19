import random
from typing import Dict, List, Set
import time
from dataclasses import dataclass
from threading import Thread, Lock
import logging

@dataclass
class Message:
    """Represents a message in the gossip network"""
    id: str
    content: str
    timestamp: float
    ttl: int = 10  # Time-to-live in hops

class Node:
    def __init__(self, node_id: str, peers: List[str] = None):
        self.node_id = node_id
        self.peers = set(peers) if peers else set()
        self.messages: Dict[str, Message] = {}
        self.message_lock = Lock()
        self.running = False
        self.logger = logging.getLogger(f"Node-{node_id}")
        
    def add_peer(self, peer_id: str):
        """Add a peer to this node's network"""
        if peer_id != self.node_id:
            self.peers.add(peer_id)
            
    def remove_peer(self, peer_id: str):
        """Remove a peer from this node's network"""
        self.peers.discard(peer_id)
        
    def broadcast(self, content: str):
        """Create and broadcast a new message to the network"""
        message = Message(
            id=f"{self.node_id}-{time.time()}",
            content=content,
            timestamp=time.time()
        )
        with self.message_lock:
            self.messages[message.id] = message
        self.logger.info(f"Broadcasting message: {message.content}")
        
    def receive_message(self, message: Message) -> bool:
        """
        Process a received message. Returns True if message was new and processed,
        False if it was already seen.
        """
        if message.ttl <= 0:
            return False
            
        with self.message_lock:
            if message.id in self.messages:
                return False
                
            message.ttl -= 1
            self.messages[message.id] = message
            self.logger.info(f"Received new message: {message.content}")
            return True
            
    def gossip(self):
        """Randomly select a peer and share a random message"""
        if not self.peers:
            return
            
        # Select random peer
        peer = random.choice(list(self.peers))
        
        # Select random message to share
        with self.message_lock:
            if not self.messages:
                return
            message = random.choice(list(self.messages.values()))
            
        # In a real implementation, this would actually send to the peer
        self.logger.info(f"Gossiping message {message.id} to peer {peer}")
        
    def start_gossip(self, interval: float = 1.0):
        """Start the gossip process in a background thread"""
        self.running = True
        
        def _gossip_loop():
            while self.running:
                self.gossip()
                time.sleep(interval)
                
        Thread(target=_gossip_loop, daemon=True).start()
        
    def stop_gossip(self):
        """Stop the gossip process"""
        self.running = False

# Example usage
def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create a simple network of nodes
    nodes = [
        Node(f"node{i}", [f"node{j}" for j in range(5) if j != i])
        for i in range(5)
    ]
    
    # Start gossip process for all nodes
    for node in nodes:
        node.start_gossip()
    
    # Broadcast a message from node0
    nodes[0].broadcast("Hello from node0!")
    
    # Let the gossip protocol run for a while
    time.sleep(10)
    
    # Stop all nodes
    for node in nodes:
        node.stop_gossip()
        
if __name__ == "__main__":
    main()
