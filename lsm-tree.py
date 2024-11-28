from collections import defaultdict
import bisect
from typing import Any, List, Dict, Optional, Tuple

class MemTable:
    def __init__(self, size_threshold: int = 5):
        self.data = {}
        self.size_threshold = size_threshold
        
    def put(self, key: Any, value: Any) -> bool:
        """Insert a key-value pair into memtable. Returns True if table is full."""
        self.data[key] = value
        return len(self.data) >= self.size_threshold
    
    def get(self, key: Any) -> Optional[Any]:
        """Retrieve value for key if it exists."""
        return self.data.get(key)
    
    def to_sorted_list(self) -> List[Tuple[Any, Any]]:
        """Convert memtable to sorted list of key-value pairs."""
        return sorted(self.data.items(), key=lambda x: x[0])

class SSTable:
    def __init__(self, data: List[Tuple[Any, Any]]):
        """Initialize SSTable with sorted data."""
        self.data = data
        self.keys = [item[0] for item in data]
        
    def get(self, key: Any) -> Optional[Any]:
        """Binary search for key in SSTable."""
        idx = bisect.bisect_left(self.keys, key)
        if idx < len(self.keys) and self.keys[idx] == key:
            return self.data[idx][1]
        return None

class LSMTree:
    def __init__(self, memtable_size: int = 5, max_levels: int = 4):
        """
        Initialize LSM Tree with specified memtable size and maximum levels.
        
        Args:
            memtable_size: Number of entries before memtable is flushed
            max_levels: Maximum number of levels in the tree
        """
        self.memtable = MemTable(memtable_size)
        self.levels: List[List[SSTable]] = [[] for _ in range(max_levels)]
        self.max_levels = max_levels
        
    def put(self, key: Any, value: Any) -> None:
        """Insert a key-value pair into the LSM tree."""
        if self.memtable.put(key, value):
            self._flush_memtable()
            self.memtable = MemTable(self.memtable.size_threshold)
            
    def get(self, key: Any) -> Optional[Any]:
        """
        Retrieve value for key from LSM tree.
        Returns most recent value or None if key doesn't exist.
        """
        # First check memtable
        value = self.memtable.get(key)
        if value is not None:
            return value
            
        # Then check each level, starting from most recent
        for level in self.levels:
            for sstable in reversed(level):
                value = sstable.get(key)
                if value is not None:
                    return value
        return None
    
    def _flush_memtable(self) -> None:
        """Flush memtable to level 0 and trigger compaction if needed."""
        # Convert memtable to SSTable
        sstable = SSTable(self.memtable.to_sorted_list())
        self.levels[0].append(sstable)
        
        # Check if compaction is needed at any level
        for level in range(len(self.levels) - 1):
            if len(self.levels[level]) > (1 << level):  # if level has too many tables
                self._compact_level(level)
    
    def _compact_level(self, level: int) -> None:
        """
        Compact a level by merging all its SSTables with the next level.
        """
        if level >= self.max_levels - 1:
            return
            
        # Merge all tables in current level
        current_data = []
        for table in self.levels[level]:
            current_data.extend(table.data)
            
        # Merge with next level's tables
        next_data = []
        for table in self.levels[level + 1]:
            next_data.extend(table.data)
            
        # Combine and sort all data
        merged_data = sorted(current_data + next_data, key=lambda x: x[0])
        
        # Remove duplicates, keeping only most recent value for each key
        deduped_data = []
        seen_keys = set()
        for key, value in reversed(merged_data):
            if key not in seen_keys:
                deduped_data.append((key, value))
                seen_keys.add(key)
        deduped_data.reverse()
        
        # Clear both levels
        self.levels[level].clear()
        self.levels[level + 1] = [SSTable(deduped_data)]
