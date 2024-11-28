import os
import json
import time
import bisect
import hashlib
import threading
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Tombstone:
    """Represents a deleted entry."""
    timestamp: float
    
@dataclass
class SSTableIndex:
    """Index entry for SSTable."""
    key: str
    position: int
    timestamp: float

class CommitLog:
    """Cassandra-style commit log for durability."""
    def __init__(self, directory: str):
        self.directory = directory
        self.current_segment = None
        self.segment_size = 32 * 1024 * 1024  # 32MB
        self.current_position = 0
        os.makedirs(directory, exist_ok=True)
        self._init_new_segment()
        
    def _init_new_segment(self):
        """Initialize a new commit log segment."""
        timestamp = int(time.time() * 1000)
        filename = os.path.join(self.directory, f"commitlog-{timestamp}.log")
        self.current_segment = open(filename, 'ab+')
        self.current_position = 0
        
    def append(self, key: str, value: Any, timestamp: float) -> None:
        """Append mutation to commit log."""
        entry = {
            'key': key,
            'value': value,
            'timestamp': timestamp
        }
        serialized = json.dumps(entry).encode('utf-8') + b'\n'
        
        if self.current_position + len(serialized) > self.segment_size:
            self.current_segment.close()
            self._init_new_segment()
            
        self.current_segment.write(serialized)
        self.current_segment.flush()
        os.fsync(self.current_segment.fileno())
        self.current_position += len(serialized)
        
    def truncate(self):
        """Truncate commit log after successful flush."""
        self.current_segment.close()
        self._init_new_segment()

class BloomFilter:
    """Bloom filter for SSTable lookups."""
    def __init__(self, size: int = 1000000, num_hashes: int = 3):
        self.size = size
        self.num_hashes = num_hashes
        self.bit_array = [False] * size
        
    def _get_hash_values(self, key: str) -> List[int]:
        """Generate hash values for key."""
        values = []
        for i in range(self.num_hashes):
            hash_input = f"{key}:{i}".encode('utf-8')
            hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
            values.append(hash_value % self.size)
        return values
        
    def add(self, key: str):
        """Add key to Bloom filter."""
        for pos in self._get_hash_values(key):
            self.bit_array[pos] = True
            
    def might_contain(self, key: str) -> bool:
        """Check if key might be in set."""
        return all(self.bit_array[pos] for pos in self._get_hash_values(key))

class SSTable:
    """Sorted String Table implementation."""
    def __init__(self, table_id: int, directory: str):
        self.table_id = table_id
        self.directory = directory
        self.data_file = os.path.join(directory, f"data-{table_id}.db")
        self.index_file = os.path.join(directory, f"index-{table_id}.db")
        self.bloom_filter = BloomFilter()
        self.index: List[SSTableIndex] = []
        
    def write(self, data: Dict[str, Any], timestamps: Dict[str, float]):
        """Write sorted data to SSTable."""
        with open(self.data_file, 'wb') as df, open(self.index_file, 'wb') as if_:
            position = 0
            
            for key in sorted(data.keys()):
                # Write data entry
                entry = {
                    'key': key,
                    'value': data[key],
                    'timestamp': timestamps[key]
                }
                serialized = json.dumps(entry).encode('utf-8') + b'\n'
                df.write(serialized)
                
                # Update index
                index_entry = SSTableIndex(key, position, timestamps[key])
                self.index.append(index_entry)
                if_.write(json.dumps(vars(index_entry)).encode('utf-8') + b'\n')
                
                # Update bloom filter
                self.bloom_filter.add(key)
                
                position += len(serialized)
                
    def get(self, key: str) -> Optional[Tuple[Any, float]]:
        """Retrieve value and timestamp for key."""
        if not self.bloom_filter.might_contain(key):
            return None
            
        # Binary search in index
        left = 0
        right = len(self.index) - 1
        
        while left <= right:
            mid = (left + right) // 2
            index_entry = self.index[mid]
            
            if index_entry.key == key:
                # Found key in index, read from data file
                with open(self.data_file, 'rb') as f:
                    f.seek(index_entry.position)
                    entry = json.loads(f.readline().decode('utf-8'))
                    return entry['value'], entry['timestamp']
            elif index_entry.key < key:
                left = mid + 1
            else:
                right = mid - 1
                
        return None

class Memtable:
    """In-memory sorted structure for recent writes."""
    def __init__(self, threshold_bytes: int = 64 * 1024 * 1024):  # 64MB
        self.data: Dict[str, Any] = {}
        self.timestamps: Dict[str, float] = {}
        self.size_bytes = 0
        self.threshold_bytes = threshold_bytes
        self.lock = threading.RLock()
        
    def put(self, key: str, value: Any) -> bool:
        """Insert key-value pair. Returns True if memtable is full."""
        with self.lock:
            timestamp = time.time()
            entry_size = len(key) + len(str(value))
            
            if key in self.data:
                self.size_bytes -= len(key) + len(str(self.data[key]))
                
            self.data[key] = value
            self.timestamps[key] = timestamp
            self.size_bytes += entry_size
            
            return self.size_bytes >= self.threshold_bytes
            
    def get(self, key: str) -> Optional[Tuple[Any, float]]:
        """Get value and timestamp for key."""
        with self.lock:
            if key in self.data:
                return self.data[key], self.timestamps[key]
            return None
            
    def delete(self, key: str):
        """Mark key as deleted using a tombstone."""
        with self.lock:
            self.data[key] = Tombstone(time.time())
            
    def is_empty(self) -> bool:
        """Check if memtable is empty."""
        with self.lock:
            return len(self.data) == 0

class CassandraLSM:
    """Cassandra-style LSM tree implementation."""
    def __init__(self, 
                 directory: str,
                 memtable_threshold: int = 64 * 1024 * 1024,  # 64MB
                 compaction_threshold: int = 4):
        self.directory = directory
        self.memtable = Memtable(memtable_threshold)
        self.immutable_memtable: Optional[Memtable] = None
        self.sstables: List[SSTable] = []
        self.commit_log = CommitLog(os.path.join(directory, "commit_log"))
        self.compaction_threshold = compaction_threshold
        self.next_table_id = 0
        self.lock = threading.RLock()
        
        os.makedirs(directory, exist_ok=True)
        self._load_existing_sstables()
        
        # Start background flush thread
        self.flush_thread = threading.Thread(target=self._background_flush, daemon=True)
        self.flush_thread.start()
        
        # Start background compaction thread
        self.compaction_thread = threading.Thread(target=self._background_compact, daemon=True)
        self.compaction_thread.start()
        
    def _load_existing_sstables(self):
        """Load existing SSTables from disk."""
        for filename in os.listdir(self.directory):
            if filename.startswith("data-"):
                table_id = int(filename.split("-")[1].split(".")[0])
                sstable = SSTable(table_id, self.directory)
                self.sstables.append(sstable)
                self.next_table_id = max(self.next_table_id, table_id + 1)
                
    def put(self, key: str, value: Any):
        """Insert or update key-value pair."""
        with self.lock:
            # Write to commit log first
            self.commit_log.append(key, value, time.time())
            
            # Write to memtable
            if self.memtable.put(key, value):
                # Memtable is full, mark it as immutable
                self.immutable_memtable = self.memtable
                self.memtable = Memtable(self.memtable.threshold_bytes)
                
    def get(self, key: str) -> Optional[Any]:
        """Retrieve latest value for key."""
        # Check memtable first
        result = self.memtable.get(key)
        if result:
            value, timestamp = result
            if isinstance(value, Tombstone):
                return None
            return value
            
        # Check immutable memtable if exists
        if self.immutable_memtable:
            result = self.immutable_memtable.get(key)
            if result:
                value, timestamp = result
                if isinstance(value, Tombstone):
                    return None
                return value
                
        # Check SSTables in reverse order (newest first)
        latest_value = None
        latest_timestamp = float('-inf')
        
        for sstable in reversed(self.sstables):
            result = sstable.get(key)
            if result:
                value, timestamp = result
                if timestamp > latest_timestamp:
                    latest_value = value
                    latest_timestamp = timestamp
                    
        if isinstance(latest_value, Tombstone):
            return None
        return latest_value
        
    def delete(self, key: str):
        """Delete key using tombstone."""
        with self.lock:
            self.memtable.delete(key)
            
    def _background_flush(self):
        """Background thread for flushing immutable memtable."""
        while True:
            time.sleep(1)
            
            with self.lock:
                if self.immutable_memtable and not self.immutable_memtable.is_empty():
                    # Create new SSTable
                    sstable = SSTable(self.next_table_id, self.directory)
                    self.next_table_id += 1
                    
                    # Write memtable data to SSTable
                    sstable.write(
                        self.immutable_memtable.data,
                        self.immutable_memtable.timestamps
                    )
                    
                    # Add to SSTables list
                    self.sstables.append(sstable)
                    
                    # Clear immutable memtable
                    self.immutable_memtable = None
                    
                    # Truncate commit log
                    self.commit_log.truncate()
                    
    def _background_compact(self):
        """Background thread for compaction."""
        while True:
            time.sleep(10)
            
            with self.lock:
                if len(self.sstables) >= self.compaction_threshold:
                    self._perform_compaction()
                    
    def _perform_compaction(self):
        """Perform size-tiered compaction."""
        # Sort SSTables by size
        sstables_by_size = sorted(
            self.sstables,
            key=lambda ss: os.path.getsize(ss.data_file)
        )
        
        # Take smallest SSTables for compaction
        tables_to_compact = sstables_by_size[:self.compaction_threshold]
        
        # Merge data from all tables
        merged_data = {}
        merged_timestamps = {}
        
        for sstable in tables_to_compact:
            with open(sstable.data_file, 'rb') as f:
                for line in f:
                    entry = json.loads(line.decode('utf-8'))
                    key = entry['key']
                    timestamp = entry['timestamp']
                    
                    if key not in merged_timestamps or timestamp > merged_timestamps[key]:
                        merged_data[key] = entry['value']
                        merged_timestamps[key] = timestamp
                        
        # Create new SSTable with merged data
        new_sstable = SSTable(self.next_table_id, self.directory)
        self.next_table_id += 1
        new_sstable.write(merged_data, merged_timestamps)
        
        # Replace old SSTables with new one
        self.sstables = [
            ss for ss in self.sstables
            if ss not in tables_to_compact
        ]
        self.sstables.append(new_sstable)
        
        # Delete old SSTable files
        for sstable in tables_to_compact:
            os.remove(sstable.data_file)
            os.remove(sstable.index_file)
