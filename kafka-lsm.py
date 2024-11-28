import os
import json
import time
import threading
from typing import Any, Dict, List, Optional, Iterator, Tuple
from collections import OrderedDict
from pathlib import Path

class Segment:
    """Represents an immutable log segment file."""
    def __init__(self, base_dir: str, segment_id: int):
        self.base_dir = base_dir
        self.segment_id = segment_id
        self.filename = os.path.join(base_dir, f"segment-{segment_id}.log")
        self.index: Dict[Any, int] = {}  # key -> file offset
        self._load_index()
        
    def _load_index(self):
        """Load index from segment file."""
        if not os.path.exists(self.filename):
            return
            
        with open(self.filename, 'r') as f:
            offset = 0
            while True:
                line = f.readline()
                if not line:
                    break
                    
                entry = json.loads(line)
                self.index[entry['key']] = offset
                offset = f.tell()
    
    def append(self, key: Any, value: Any) -> int:
        """Append key-value pair to segment file."""
        entry = {
            'timestamp': time.time(),
            'key': key,
            'value': value
        }
        
        with open(self.filename, 'a') as f:
            offset = f.tell()
            f.write(json.dumps(entry) + '\n')
            f.flush()
            os.fsync(f.fileno())
            
        self.index[key] = offset
        return offset
    
    def get(self, key: Any) -> Optional[Any]:
        """Retrieve value for key from segment."""
        offset = self.index.get(key)
        if offset is None:
            return None
            
        with open(self.filename, 'r') as f:
            f.seek(offset)
            entry = json.loads(f.readline())
            return entry['value']
            
    def iter_entries(self) -> Iterator[Tuple[Any, Any]]:
        """Iterate through all entries in segment."""
        with open(self.filename, 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                    
                entry = json.loads(line)
                yield entry['key'], entry['value']
    
    def size(self) -> int:
        """Get size of segment file in bytes."""
        return os.path.getsize(self.filename)

class MemTable:
    """In-memory buffer for recent writes."""
    def __init__(self, size_threshold: int):
        self.data = OrderedDict()
        self.size_threshold = size_threshold
        self.size = 0
        self.lock = threading.RLock()
    
    def put(self, key: Any, value: Any) -> bool:
        """Add key-value pair to memtable. Returns True if table is full."""
        with self.lock:
            self.data[key] = value
            self.size += len(str(key)) + len(str(value))
            return self.size >= self.size_threshold
    
    def get(self, key: Any) -> Optional[Any]:
        """Retrieve value for key."""
        with self.lock:
            return self.data.get(key)
    
    def items(self) -> List[Tuple[Any, Any]]:
        """Get all items in insertion order."""
        with self.lock:
            return list(self.data.items())

class KafkaLSMTree:
    """Kafka-style LSM tree using append-only logs."""
    def __init__(self, 
                 base_dir: str,
                 memtable_size: int = 1024 * 1024,  # 1MB
                 segment_size: int = 1024 * 1024 * 10,  # 10MB
                 compaction_threshold: int = 4):  # Compact after 4 segments
        self.base_dir = base_dir
        self.memtable_size = memtable_size
        self.segment_size = segment_size
        self.compaction_threshold = compaction_threshold
        
        self.memtable = MemTable(memtable_size)
        self.segments: List[Segment] = []
        self.next_segment_id = 0
        self.lock = threading.RLock()
        
        # Create base directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)
        
        # Load existing segments
        self._load_segments()
        
        # Start background compaction thread
        self.compaction_thread = threading.Thread(target=self._compaction_loop, daemon=True)
        self.compaction_thread.start()
    
    def _load_segments(self):
        """Load existing segments from disk."""
        segment_files = sorted(Path(self.base_dir).glob("segment-*.log"))
        for segment_file in segment_files:
            segment_id = int(segment_file.stem.split('-')[1])
            self.segments.append(Segment(self.base_dir, segment_id))
            self.next_segment_id = max(self.next_segment_id, segment_id + 1)
    
    def put(self, key: Any, value: Any):
        """Write key-value pair to LSM tree."""
        with self.lock:
            if self.memtable.put(key, value):
                self._flush_memtable()
    
    def get(self, key: Any) -> Optional[Any]:
        """Retrieve value for key."""
        # Check memtable first
        value = self.memtable.get(key)
        if value is not None:
            return value
        
        # Check segments in reverse order (newest first)
        for segment in reversed(self.segments):
            value = segment.get(key)
            if value is not None:
                return value
        
        return None
    
    def _flush_memtable(self):
        """Flush memtable to new segment."""
        # Create new segment
        segment = Segment(self.base_dir, self.next_segment_id)
        self.next_segment_id += 1
        
        # Write memtable entries to segment
        for key, value in self.memtable.items():
            segment.append(key, value)
        
        # Add segment to list
        self.segments.append(segment)
        
        # Create new memtable
        self.memtable = MemTable(self.memtable_size)
    
    def _compaction_loop(self):
        """Background thread for segment compaction."""
        while True:
            time.sleep(10)  # Check every 10 seconds
            
            with self.lock:
                if len(self.segments) >= self.compaction_threshold:
                    self._compact_segments()
    
    def _compact_segments(self):
        """Compact segments by merging and removing duplicates."""
        # Create new segment for compacted data
        compact_segment = Segment(self.base_dir, self.next_segment_id)
        self.next_segment_id += 1
        
        # Track latest value for each key
        latest_values: Dict[Any, Any] = {}
        
        # Collect latest values from all segments
        for segment in self.segments:
            for key, value in segment.iter_entries():
                latest_values[key] = value
        
        # Write compacted data to new segment
        for key, value in latest_values.items():
            compact_segment.append(key, value)
        
        # Replace old segments with compacted segment
        old_segments = self.segments
        self.segments = [compact_segment]
        
        # Delete old segment files
        for segment in old_segments:
            os.remove(segment.filename)
    
    def iter_all(self) -> Iterator[Tuple[Any, Any]]:
        """Iterate through all key-value pairs."""
        # Track seen keys to avoid duplicates
        seen_keys = set()
        
        # First yield from memtable
        for key, value in self.memtable.items():
            seen_keys.add(key)
            yield key, value
        
        # Then yield from segments in reverse order
        for segment in reversed(self.segments):
            for key, value in segment.iter_entries():
                if key not in seen_keys:
                    seen_keys.add(key)
                    yield key, value

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the LSM tree."""
        return {
            'num_segments': len(self.segments),
            'total_segments_size': sum(segment.size() for segment in self.segments),
            'memtable_size': self.memtable.size,
            'memtable_entries': len(self.memtable.data),
            'total_entries': sum(len(segment.index) for segment in self.segments) + len(self.memtable.data)
        }
