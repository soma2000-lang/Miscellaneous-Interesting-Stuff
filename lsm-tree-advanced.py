import os
import json
import mmh3
import bisect
import pickle
import mmap
from typing import Any, List, Dict, Optional, Tuple, Set
from collections import defaultdict
from datetime import datetime
import threading
from pathlib import Path

class BloomFilter:
    def __init__(self, expected_elements: int, false_positive_rate: float = 0.01):
        """Initialize Bloom filter with desired false positive rate."""
        self.size = self._calculate_size(expected_elements, false_positive_rate)
        self.hash_functions = self._calculate_hash_functions(self.size, expected_elements)
        self.bit_array = [False] * self.size
        
    def _calculate_size(self, n: int, p: float) -> int:
        """Calculate optimal size of bit array."""
        return int(-n * math.log(p) / (math.log(2) ** 2))
    
    def _calculate_hash_functions(self, m: int, n: int) -> int:
        """Calculate optimal number of hash functions."""
        return int((m / n) * math.log(2))
    
    def add(self, key: Any) -> None:
        """Add key to Bloom filter."""
        for seed in range(self.hash_functions):
            index = mmh3.hash(str(key), seed) % self.size
            self.bit_array[index] = True
    
    def might_contain(self, key: Any) -> bool:
        """Check if key might be in set."""
        return all(
            self.bit_array[mmh3.hash(str(key), seed) % self.size]
            for seed in range(self.hash_functions)
        )

class WriteAheadLog:
    def __init__(self, path: str):
        self.path = path
        self.current_file = None
        self.current_position = 0
        self._ensure_directory()
        self._open_current_file()
        
    def _ensure_directory(self):
        """Create WAL directory if it doesn't exist."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        
    def _open_current_file(self):
        """Open current WAL file for appending."""
        self.current_file = open(self.path, 'ab+')
        self.current_position = self.current_file.tell()
        
    def append(self, operation: str, key: Any, value: Any) -> None:
        """Append operation to WAL."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'key': key,
            'value': value
        }
        serialized = json.dumps(entry) + '\n'
        self.current_file.write(serialized.encode())
        self.current_file.flush()
        os.fsync(self.current_file.fileno())
        
    def recover(self) -> List[dict]:
        """Recover operations from WAL file."""
        operations = []
        with open(self.path, 'rb') as f:
            for line in f:
                try:
                    entry = json.loads(line.decode())
                    operations.append(entry)
                except:
                    # Corrupted entry, stop recovery here
                    break
        return operations
    
    def truncate(self):
        """Truncate WAL after successful flush."""
        self.current_file.close()
        self.current_file = open(self.path, 'w+b')
        self.current_position = 0

class MemTable:
    def __init__(self, size_threshold: int = 5):
        self.data = {}
        self.size_threshold = size_threshold
        self.lock = threading.RLock()
        
    def put(self, key: Any, value: Any) -> bool:
        """Thread-safe insert into memtable."""
        with self.lock:
            self.data[key] = value
            return len(self.data) >= self.size_threshold
    
    def get(self, key: Any) -> Optional[Any]:
        """Thread-safe retrieval from memtable."""
        with self.lock:
            return self.data.get(key)
    
    def to_sorted_list(self) -> List[Tuple[Any, Any]]:
        """Convert memtable to sorted list with thread safety."""
        with self.lock:
            return sorted(self.data.items(), key=lambda x: x[0])

class SSTable:
    def __init__(self, data: List[Tuple[Any, Any]], table_id: int, level: int):
        """Initialize SSTable with sorted data and metadata."""
        self.table_id = table_id
        self.level = level
        self.data = data
        self.keys = [item[0] for item in data]
        self.bloom_filter = BloomFilter(len(data))
        self._build_bloom_filter()
        self._write_to_disk()
        
    def _build_bloom_filter(self):
        """Build Bloom filter for all keys."""
        for key, _ in self.data:
            self.bloom_filter.add(key)
            
    def _write_to_disk(self):
        """Write SSTable to disk using memory mapping."""
        filename = f"sstable_L{self.level}_{self.table_id}.db"
        with open(filename, 'wb') as f:
            # Write metadata
            metadata = {
                'table_id': self.table_id,
                'level': self.level,
                'size': len(self.data)
            }
            pickle.dump(metadata, f)
            # Write actual data
            pickle.dump(self.data, f)
            # Write Bloom filter
            pickle.dump(self.bloom_filter, f)
            
    def get(self, key: Any) -> Optional[Any]:
        """Get value for key using Bloom filter and binary search."""
        if not self.bloom_filter.might_contain(key):
            return None
            
        idx = bisect.bisect_left(self.keys, key)
        if idx < len(self.keys) and self.keys[idx] == key:
            return self.data[idx][1]
        return None

class CompactionStrategy:
    def __init__(self, max_level_size: List[int]):
        self.max_level_size = max_level_size
        
    def should_compact(self, level: int, current_size: int) -> bool:
        """Determine if level needs compaction."""
        return current_size > self.max_level_size[level]
        
    def choose_files_to_compact(self, level: int, sstables: List[SSTable]) -> List[SSTable]:
        """Choose which SSTables to include in compaction."""
        if level == 0:
            # Compact all files in level 0
            return sstables
        else:
            # Size-tiered compaction for other levels
            return sorted(sstables, key=lambda x: len(x.data))[:2]

class LSMTree:
    def __init__(self, 
                 memtable_size: int = 5, 
                 max_levels: int = 4,
                 wal_path: str = "wal/wal.log"):
        """
        Initialize LSM Tree with advanced features.
        
        Args:
            memtable_size: Number of entries before memtable is flushed
            max_levels: Maximum number of levels in the tree
            wal_path: Path to write-ahead log file
        """
        self.memtable = MemTable(memtable_size)
        self.immutable_memtable = None
        self.levels: List[List[SSTable]] = [[] for _ in range(max_levels)]
        self.max_levels = max_levels
        self.wal = WriteAheadLog(wal_path)
        self.next_table_id = 0
        self.compaction_strategy = CompactionStrategy([4, 8, 16, 32])  # Example sizes
        self.lock = threading.RLock()
        
        # Recovery from WAL if exists
        self._recover_from_wal()
        
    def _recover_from_wal(self):
        """Recover state from write-ahead log."""
        operations = self.wal.recover()
        for op in operations:
            if op['operation'] == 'PUT':
                self.memtable.put(op['key'], op['value'])
                
    def put(self, key: Any, value: Any) -> None:
        """Thread-safe put operation with WAL."""
        with self.lock:
            # Write to WAL first
            self.wal.append('PUT', key, value)
            
            # Write to memtable
            if self.memtable.put(key, value):
                # Memtable is full, create new one
                self.immutable_memtable = self.memtable
                self.memtable = MemTable(self.memtable.size_threshold)
                
                # Flush immutable memtable in background
                threading.Thread(target=self._flush_immutable_memtable).start()
            
    def get(self, key: Any) -> Optional[Any]:
        """Thread-safe get operation using Bloom filters."""
        with self.lock:
            # Check memtable first
            value = self.memtable.get(key)
            if value is not None:
                return value
                
            # Check immutable memtable if exists
            if self.immutable_memtable:
                value = self.immutable_memtable.get(key)
                if value is not None:
                    return value
                    
            # Check each level, using Bloom filters to skip tables
            for level in self.levels:
                for sstable in reversed(level):
                    value = sstable.get(key)
                    if value is not None:
                        return value
            return None
            
    def _flush_immutable_memtable(self):
        """Flush immutable memtable to level 0."""
        with self.lock:
            if not self.immutable_memtable:
                return
                
            # Create new SSTable
            sstable = SSTable(
                self.immutable_memtable.to_sorted_list(),
                self.next_table_id,
                0
            )
            self.next_table_id += 1
            self.levels[0].append(sstable)
            
            # Clear immutable memtable
            self.immutable_memtable = None
            
            # Truncate WAL
            self.wal.truncate()
            
            # Check if compaction is needed
            self._check_compaction(0)
            
    def _check_compaction(self, level: int):
        """Check if compaction is needed at given level."""
        if level >= self.max_levels - 1:
            return
            
        if self.compaction_strategy.should_compact(level, len(self.levels[level])):
            self._compact_level(level)
            
    def _compact_level(self, level: int):
        """Perform compaction on a level."""
        # Choose files to compact
        files_to_compact = self.compaction_strategy.choose_files_to_compact(
            level, self.levels[level]
        )
        
        # Merge selected files with next level
        merged_data = []
        for sstable in files_to_compact:
            merged_data.extend(sstable.data)
            
        if level + 1 < self.max_levels:
            for sstable in self.levels[level + 1]:
                merged_data.extend(sstable.data)
                
        # Sort and deduplicate
        merged_data.sort(key=lambda x: x[0])
        deduped_data = []
        seen_keys = set()
        
        for key, value in reversed(merged_data):
            if key not in seen_keys:
                deduped_data.append((key, value))
                seen_keys.add(key)
        deduped_data.reverse()
        
        # Create new SSTable in next level
        new_sstable = SSTable(deduped_data, self.next_table_id, level + 1)
        self.next_table_id += 1
        
        # Update levels
        self.levels[level] = [
            table for table in self.levels[level]
            if table not in files_to_compact
        ]
        self.levels[level + 1] = [new_sstable]
        
        # Check if next level needs compaction
        self._check_compaction(level + 1)

class LSMTreeIterator:
    """Iterator for scanning LSM tree data."""
    def __init__(self, lsm_tree: LSMTree, start_key: Any = None, end_key: Any = None):
        self.lsm_tree = lsm_tree
        self.start_key = start_key
        self.end_key = end_key
        self.current_iterators = self._setup_iterators()
        
    def _setup_iterators(self):
        """Setup iterators for each level."""
        iterators = []
        
        # Add memtable iterator
        memtable_data = sorted(self.lsm_tree.memtable.data.items())
        iterators.append(iter(memtable_data))
        
        # Add immutable memtable iterator if exists
        if self.lsm_tree.immutable_memtable:
            immutable_data = sorted(self.lsm_tree.immutable_memtable.data.items())
            iterators.append(iter(immutable_data))
            
        # Add SSTable iterators
        for level in self.lsm_tree.levels:
            for sstable in level:
                iterators.append(iter(sstable.data))
                
        return iterators
        
    def __iter__(self):
        return self
        
    def __next__(self):
        """Get next item from merged iterators."""
        min_key = None
        min_value = None
        min_iterator = None
        
        # Find minimum key across all iterators
        for iterator in self.current_iterators:
            try:
                key, value = next(iterator)
                if self.end_key and key > self.end_key:
                    continue
                if self.start_key and key < self.start_key:
                    continue
                if min_key is None or key < min_key:
                    min_key = key
                    min_value = value
                    min_iterator = iterator
            except StopIteration:
                continue
                
        if min_key is None:
            raise StopIteration
            
        return min_key, min_value
