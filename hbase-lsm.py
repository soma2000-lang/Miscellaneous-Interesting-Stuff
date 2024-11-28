import os
import json
import time
import heapq
import struct
import threading
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

class KeyValue:
    """HBase KeyValue format."""
    def __init__(self, row: str, family: str, qualifier: str, value: Any, timestamp: int = None):
        self.row = row
        self.family = family
        self.qualifier = qualifier
        self.value = value
        self.timestamp = timestamp or int(time.time() * 1000)
        
    def to_bytes(self) -> bytes:
        """Serialize KeyValue to bytes."""
        row_bytes = self.row.encode('utf-8')
        family_bytes = self.family.encode('utf-8')
        qualifier_bytes = self.qualifier.encode('utf-8')
        value_bytes = json.dumps(self.value).encode('utf-8')
        
        return struct.pack(
            f'>I{len(row_bytes)}s'
            f'B{len(family_bytes)}s'
            f'I{len(qualifier_bytes)}s'
            f'Q'
            f'I{len(value_bytes)}s',
            len(row_bytes), row_bytes,
            len(family_bytes), family_bytes,
            len(qualifier_bytes), qualifier_bytes,
            self.timestamp,
            len(value_bytes), value_bytes
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'KeyValue':
        """Deserialize KeyValue from bytes."""
        pos = 0
        
        # Read row
        row_len = struct.unpack('>I', data[pos:pos+4])[0]
        pos += 4
        row = data[pos:pos+row_len].decode('utf-8')
        pos += row_len
        
        # Read family
        family_len = struct.unpack('B', data[pos:pos+1])[0]
        pos += 1
        family = data[pos:pos+family_len].decode('utf-8')
        pos += family_len
        
        # Read qualifier
        qualifier_len = struct.unpack('>I', data[pos:pos+4])[0]
        pos += 4
        qualifier = data[pos:pos+qualifier_len].decode('utf-8')
        pos += qualifier_len
        
        # Read timestamp
        timestamp = struct.unpack('>Q', data[pos:pos+8])[0]
        pos += 8
        
        # Read value
        value_len = struct.unpack('>I', data[pos:pos+4])[0]
        pos += 4
        value = json.loads(data[pos:pos+value_len].decode('utf-8'))
        
        return cls(row, family, qualifier, value, timestamp)

class WAL:
    """Write-Ahead Log implementation."""
    def __init__(self, path: str):
        self.path = path
        self.current_file = None
        self.sequence_id = 0
        self._ensure_directory()
        self._open_current_file()
        
    def _ensure_directory(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        
    def _open_current_file(self):
        self.current_file = open(self.path, 'ab+')
        
    def append(self, kv: KeyValue) -> int:
        """Append KeyValue to WAL."""
        self.sequence_id += 1
        entry = {
            'sequence_id': self.sequence_id,
            'timestamp': datetime.now().isoformat(),
            'kv': {
                'row': kv.row,
                'family': kv.family,
                'qualifier': kv.qualifier,
                'value': kv.value,
                'timestamp': kv.timestamp
            }
        }
        
        serialized = json.dumps(entry) + '\n'
        self.current_file.write(serialized.encode())
        self.current_file.flush()
        os.fsync(self.current_file.fileno())
        return self.sequence_id

class BloomFilter:
    """Bloom filter for HFile block lookups."""
    def __init__(self, expected_entries: int, false_positive_rate: float = 0.01):
        self.size = self._optimal_size(expected_entries, false_positive_rate)
        self.num_hashes = self._optimal_hashes(self.size, expected_entries)
        self.bit_array = [False] * self.size
        
    def _optimal_size(self, n: int, p: float) -> int:
        return int(-n * math.log(p) / (math.log(2) ** 2))
        
    def _optimal_hashes(self, m: int, n: int) -> int:
        return int((m / n) * math.log(2))
        
    def add(self, item: Any):
        for seed in range(self.num_hashes):
            idx = hash(str(item) + str(seed)) % self.size
            self.bit_array[idx] = True
            
    def might_contain(self, item: Any) -> bool:
        return all(
            self.bit_array[hash(str(item) + str(seed)) % self.size]
            for seed in range(self.num_hashes)
        )

class HFileBlock:
    """Data block within an HFile."""
    def __init__(self, block_id: int):
        self.block_id = block_id
        self.data: List[KeyValue] = []
        self.index: Dict[str, int] = {}  # row -> offset in data
        
    def add(self, kv: KeyValue):
        offset = len(self.data)
        self.data.append(kv)
        self.index[kv.row] = offset
        
    def get(self, row: str) -> Optional[KeyValue]:
        offset = self.index.get(row)
        return self.data[offset] if offset is not None else None
        
    def serialize(self) -> bytes:
        """Serialize block data."""
        result = bytearray()
        for kv in self.data:
            kv_bytes = kv.to_bytes()
            result.extend(kv_bytes)
        return bytes(result)

class HFile:
    """HBase HFile implementation."""
    def __init__(self, path: str, block_size: int = 64 * 1024):  # 64KB blocks
        self.path = path
        self.block_size = block_size
        self.blocks: List[HFileBlock] = []
        self.bloom_filter = BloomFilter(1000)  # Adjust size as needed
        self.current_block = HFileBlock(0)
        self.current_block_size = 0
        
    def add(self, kv: KeyValue):
        """Add KeyValue to HFile."""
        kv_size = len(kv.to_bytes())
        
        if self.current_block_size + kv_size > self.block_size:
            self.blocks.append(self.current_block)
            self.current_block = HFileBlock(len(self.blocks))
            self.current_block_size = 0
            
        self.current_block.add(kv)
        self.current_block_size += kv_size
        self.bloom_filter.add(kv.row)
        
    def get(self, row: str) -> Optional[KeyValue]:
        """Get latest value for row."""
        if not self.bloom_filter.might_contain(row):
            return None
            
        # Check current block
        kv = self.current_block.get(row)
        if kv:
            return kv
            
        # Check other blocks
        for block in reversed(self.blocks):
            kv = block.get(row)
            if kv:
                return kv
                
        return None
        
    def flush(self):
        """Flush HFile to disk."""
        if self.current_block.data:
            self.blocks.append(self.current_block)
            
        with open(self.path, 'wb') as f:
            # Write file header
            header = {
                'block_size': self.block_size,
                'num_blocks': len(self.blocks)
            }
            header_bytes = json.dumps(header).encode()
            f.write(struct.pack('>I', len(header_bytes)))
            f.write(header_bytes)
            
            # Write blocks
            for block in self.blocks:
                block_data = block.serialize()
                f.write(struct.pack('>I', len(block_data)))
                f.write(block_data)

class MemStore:
    """In-memory store for recent updates."""
    def __init__(self, flush_size: int = 64 * 1024 * 1024):  # 64MB
        self.data: Dict[str, Dict[str, Dict[str, List[KeyValue]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        self.size = 0
        self.flush_size = flush_size
        self.lock = threading.RLock()
        
    def put(self, kv: KeyValue) -> bool:
        """Add KeyValue to MemStore. Returns True if flush is needed."""
        with self.lock:
            self.data[kv.row][kv.family][kv.qualifier].append(kv)
            self.size += len(kv.to_bytes())
            return self.size >= self.flush_size
            
    def get(self, row: str, family: str = None, qualifier: str = None) -> Optional[KeyValue]:
        """Get latest value for given row/family/qualifier."""
        with self.lock:
            if row not in self.data:
                return None
                
            if family is None:
                # Get latest across all families/qualifiers
                latest = None
                latest_ts = -1
                
                for fam in self.data[row].values():
                    for qual in fam.values():
                        if qual and qual[-1].timestamp > latest_ts:
                            latest = qual[-1]
                            latest_ts = latest.timestamp
                            
                return latest
                
            if family not in self.data[row]:
                return None
                
            if qualifier is None:
                # Get latest across all qualifiers in family
                latest = None
                latest_ts = -1
                
                for qual in self.data[row][family].values():
                    if qual and qual[-1].timestamp > latest_ts:
                        latest = qual[-1]
                        latest_ts = latest.timestamp
                        
                return latest
                
            if qualifier not in self.data[row][family]:
                return None
                
            versions = self.data[row][family][qualifier]
            return versions[-1] if versions else None
            
    def to_hfile(self, path: str) -> HFile:
        """Convert MemStore to HFile."""
        hfile = HFile(path)
        
        # Sort all KeyValues by row, family, qualifier, timestamp
        all_kvs = []
        for row_data in self.data.values():
            for family_data in row_data.values():
                for qualifier_data in family_data.values():
                    all_kvs.extend(qualifier_data)
                    
        all_kvs.sort(key=lambda kv: (kv.row, kv.family, kv.qualifier, -kv.timestamp))
        
        for kv in all_kvs:
            hfile.add(kv)
            
        return hfile

class HRegion:
    """HBase Region implementation."""
    def __init__(self, 
                 region_id: str,
                 base_dir: str,
                 memstore_size: int = 64 * 1024 * 1024):  # 64MB
        self.region_id = region_id
        self.base_dir = base_dir
        self.memstore = MemStore(memstore_size)
        self.hfiles: List[HFile] = []
        self.wal = WAL(os.path.join(base_dir, f"wal-{region_id}.log"))
        self.lock = threading.RLock()
        
        # Create region directory
        os.makedirs(base_dir, exist_ok=True)
        
    def put(self, row: str, family: str, qualifier: str, value: Any):
        """Put value into region."""
        with self.lock:
            kv = KeyValue(row, family, qualifier, value)
            
            # Write to WAL first
            self.wal.append(kv)
            
            # Write to MemStore
            if self.memstore.put(kv):
                self._flush_memstore()
                
    def get(self, row: str, family: str = None, qualifier: str = None) -> Optional[Any]:
        """Get latest value from region."""
        # Check MemStore first
        kv = self.memstore.get(row, family, qualifier)
        if kv:
            return kv.value
            
        # Check HFiles in reverse order
        for hfile in reversed(self.hfiles):
            kv = hfile.get(row)
            if kv and (family is None or kv.family == family) and \
               (qualifier is None or kv.qualifier == qualifier):
                return kv.value
                
        return None
        
    def _flush_memstore(self):
        """Flush MemStore to HFile."""
        hfile_path = os.path.join(
            self.base_dir,
            f"hfile-{self.region_id}-{int(time.time())}.db"
        )
        
        # Convert MemStore to HFile
        hfile = self.memstore.to_hfile(hfile_path)
        hfile.flush()
        
        # Add to HFiles list
        self.hfiles.append(hfile)
        
        # Create new MemStore
        self.memstore = MemStore(self.memstore.flush_size)
        
        # Trigger compaction if needed
        if len(self.hfiles) > 3:  # Configurable threshold
            self._compact_files()
            
    def _compact_files(self):
        """Perform major compaction on HFiles."""
        # Create new HFile for compacted data
        compact_path = os.path.join(
            self.base_dir,
            f"hfile-{self.region_id}-compact-{int(time.time())}.db"
        )
        compact_file = HFile(compact_path)
        
        # Merge all HFiles using a priority queue
        pq = []
        file_iters = []
        
        for hfile in self.hfiles:
            file_iter = iter(hfile.blocks)
            try:
                block = next(file_iter)
                heapq.heappush(pq, (block.data[0].row, block, file_iter))
            except StopIteration:
                continue
                
        # Process all blocks in sorted order
        while pq:
            row, block, file_iter = heapq.heappop(pq)
            
            # Add all KeyValues from block
            for kv in block.data:
                compact_file.add(kv)
                
            # Get next block from same file
            try:
                next_block = next(file_iter)
                heapq.heappush(pq, (next_block.data[0].row, next_block, file_iter))