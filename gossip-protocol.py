import random
import time
from threading import Thread, Lock
from typing import Dict, List, Set
import socket
import json
import logging

class GossipNode:
    def __init__(self, host: str, port: int, peers: List[tuple] = None):
        """
        Initialize a gossip protocol node.
        
        Args:
            host (str): Host address for this node
            port (int): Port number for this node
            peers (List[tuple]): List of (host, port) tuples for initial peer nodes
        """
        self.host = host
        self.port = port
        self.peers = set(peers) if peers else set()
        self.messages: Dict[str, dict] = {}  # Message store
        self.seen_messages: Set[str] = set()  # Track seen message IDs
        self.lock = Lock()
        self.running = False
        self.message_ttl = 10  # Time-to-live for messages in rounds
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(f"GossipNode-{port}")
        
        # Initialize socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))

    def start(self):
        """Start the gossip node."""
        self.running = True
        
        # Start listener thread
        self.listener_thread = Thread(target=self._listen)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        
        # Start gossip thread
        self.gossip_thread = Thread(target=self._gossip_loop)
        self.gossip_thread.daemon = True
        self.gossip_thread.start()
        
        self.logger.info(f"Node started on {self.host}:{self.port}")

    def stop(self):
        """Stop the gossip node."""
        self.running = False
        self.socket.close()
        self.logger.info("Node stopped")

    def broadcast_message(self, message: dict):
        """
        Broadcast a new message to the network.
        
        Args:
            message (dict): Message to broadcast
        """
        message_id = f"{self.port}-{time.time()}"
        message_wrapper = {
            "id": message_id,
            "origin": f"{self.host}:{self.port}",
            "timestamp": time.time(),
            "ttl": self.message_ttl,
            "data": message
        }
        
        with self.lock:
            self.messages[message_id] = message_wrapper
            self.seen_messages.add(message_id)
        
        self.logger.info(f"Broadcasting message: {message_id}")

    def add_peer(self, host: str, port: int):
        """
        Add a new peer to the network.
        
        Args:
            host (str): Peer's host address
            port (int): Peer's port number
        """
        self.peers.add((host, port))
        self.logger.info(f"Added peer: {host}:{port}")

    def _listen(self):
        """Listen for incoming messages."""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(65535)
                message = json.loads(data.decode())
                self._handle_message(message)
            except Exception as e:
                self.logger.error(f"Error in listener: {e}")

    def _handle_message(self, message: dict):
        """
        Handle received message.
        
        Args:
            message (dict): Received message
        """
        message_id = message["id"]
        
        with self.lock:
            if message_id not in self.seen_messages and message["ttl"] > 0:
                self.seen_messages.add(message_id)
                self.messages[message_id] = message
                self.logger.info(f"Received new message: {message_id}")

    def _gossip_loop(self):
        """Main gossip loop for message propagation."""
        while self.running:
            if self.peers and self.messages:
                # Select random peer
                peer = random.choice(list(self.peers))
                
                # Select messages to send
                with self.lock:
                    # Filter messages by TTL and create copy
                    valid_messages = {k: v.copy() for k, v in self.messages.items() 
                                   if v["ttl"] > 0}
                    
                    # Decrease TTL for sent messages
                    for msg in valid_messages.values():
                        msg["ttl"] -= 1
                    
                    # Update original messages
                    for msg_id, msg in valid_messages.items():
                        self.messages[msg_id]["ttl"] = msg["ttl"]
                        
                        # Remove expired messages
                        if msg["ttl"] <= 0:
                            del self.messages[msg_id]
                
                if valid_messages:
                    try:
                        # Send messages to peer
                        data = json.dumps(list(valid_messages.values())).encode()
                        self.socket.sendto(data, peer)
                        self.logger.debug(f"Sent {len(valid_messages)} messages to {peer}")
                    except Exception as e:
                        self.logger.error(f"Error sending to peer {peer}: {e}")
                        self.peers.remove(peer)
            
            # Wait before next gossip round
            time.sleep(1)

def create_sample_network(num_nodes: int = 3, base_port: int = 5000):
    """
    Create a sample network of gossip nodes for testing.
    
    Args:
        num_nodes (int): Number of nodes to create
        base_port (int): Starting port number
    
    Returns:
        List[GossipNode]: List of created nodes
    """
    nodes = []
    
    # Create nodes
    for i in range(num_nodes):
        port = base_port + i
        peers = [(socket.gethostname(), base_port + j) 
                for j in range(num_nodes) if j != i]
        node = GossipNode(socket.gethostname(), port, peers)
        nodes.append(node)
    
    # Start all nodes
    for node in nodes:
        node.start()
    
    return nodes
