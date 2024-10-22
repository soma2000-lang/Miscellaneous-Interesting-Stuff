from typing import Any, List, Optional, Tuple, Dict
from collections import defaultdict
import math

class BTreeNode:
    def __init__(self, leaf=True):
        self.leaf = leaf
        self.keys = []
        self.children = []

class BTree:
    def __init__(self, t):
        self.root = BTreeNode()
        self.t = t  # Minimum degree

    def insert(self, k):
        root = self.root
        if len(root.keys) == (2 * self.t) - 1:
            new_root = BTreeNode(leaf=False)
            self.root = new_root
            new_root.children.insert(0, root)
            self._split_child(new_root, 0)
            self._insert_non_full(new_root, k)
        else:
            self._insert_non_full(root, k)

    def _split_child(self, parent: BTreeNode, i: int):
        t = self.t
        y = parent.children[i]
        z = BTreeNode(leaf=y.leaf)
        
        parent.keys.insert(i, y.keys[t-1])
        parent.children.insert(i + 1, z)
        
        z.keys = y.keys[t:]
        y.keys = y.keys[:t-1]
        
        if not y.leaf:
            z.children = y.children[t:]
            y.children = y.children[:t]

    def _insert_non_full(self, x: BTreeNode, k):
        i = len(x.keys) - 1
        if x.leaf:
            while i >= 0 and k < x.keys[i]:
                i -= 1
            x.keys.insert(i + 1, k)
        else:
            while i >= 0 and k < x.keys[i]:
                i -= 1
            i += 1
            if len(x.children[i].keys) == (2 * self.t) - 1:
                self._split_child(x, i)
                if k > x.keys[i]:
                    i += 1
            self._insert_non_full(x.children[i], k)

class BPlusNode:
    def __init__(self, leaf=True):
        self.leaf = leaf
        self.keys = []
        self.children = []
        self.next = None  # For leaf nodes

class BPlusTree:
    def __init__(self, order):
        self.root = BPlusNode()
        self.order = order

    def insert(self, key, value):
        if len(self.root.keys) == 0:
            self.root.keys.append(key)
            self.root.children.append([value])
            return

        leaf = self._find_leaf(self.root, key)
        self._insert_in_leaf(leaf, key, value)

    def _find_leaf(self, node: BPlusNode, key) -> BPlusNode:
        if node.leaf:
            return node
        
        for i, item in enumerate(node.keys):
            if key < item:
                return self._find_leaf(node.children[i], key)
        return self._find_leaf(node.children[-1], key)

    def _insert_in_leaf(self, node: BPlusNode, key, value):
        if len(node.keys) < self.order:
            i = 0
            while i < len(node.keys) and node.keys[i] < key:
                i += 1
            node.keys.insert(i, key)
            node.children.insert(i, [value])
        else:
            # Handle split
            pass  # Implementation omitted for brevity

class RTree:
    class Node:
        def __init__(self, leaf=True):
            self.leaf = leaf
            self.entries = []  # (MBR, child) or (MBR, data)
            self.parent = None

    def __init__(self, max_entries, min_entries):
        self.root = self.Node()
        self.max_entries = max_entries
        self.min_entries = min_entries

    def insert(self, bbox, data):
        leaf = self._choose_leaf(self.root, bbox)
        leaf.entries.append((bbox, data))
        
        if len(leaf.entries) > self.max_entries:
            self._split_node(leaf)

    def _choose_leaf(self, node, bbox):
        if node.leaf:
            return node
            
        min_increase = float('inf')
        chosen_child = None
        
        for mbr, child in node.entries:
            increase = self._calculate_enlargement(mbr, bbox)
            if increase < min_increase:
                min_increase = increase
                chosen_child = child
                
        return self._choose_leaf(chosen_child, bbox)

    def _calculate_enlargement(self, mbr1, mbr2):
        # Calculate area increase if mbr1 were to include mbr2
        return (max(mbr1[2], mbr2[2]) - min(mbr1[0], mbr2[0])) * \
               (max(mbr1[3], mbr2[3]) - min(mbr1[1], mbr2[1])) - \
               (mbr1[2] - mbr1[0]) * (mbr1[3] - mbr1[1])

class TTree:
    class Node:
        def __init__(self):
            self.values = []
            self.left = None
            self.right = None

    def __init__(self, max_items):
        self.root = None
        self.max_items = max_items

    def insert(self, value):
        if not self.root:
            self.root = self.Node()
            self.root.values.append(value)
            return

        node = self._find_node(self.root, value)
        if len(node.values) < self.max_items:
            self._insert_into_node(node, value)
        else:
            self._handle_overflow(node, value)

    def _find_node(self, node, value):
        if not node:
            return None
        
        if value < node.values[0]:
            if node.left:
                return self._find_node(node.left, value)
            return node
            
        if value > node.values[-1]:
            if node.right:
                return self._find_node(node.right, value)
            return node
            
        return node

    def _insert_into_node(self, node, value):
        i = 0
        while i < len(node.values) and node.values[i] < value:
            i += 1
        node.values.insert(i, value)

class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end = True

    def search(self, word: str) -> bool:
        node = self._traverse(word)
        return node is not None and node.is_end

    def starts_with(self, prefix: str) -> bool:
        return self._traverse(prefix) is not None

    def _traverse(self, prefix: str) -> Optional[TrieNode]:
        node = self.root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]
        return node

class SuffixTree:
    class Node:
        def __init__(self):
            self.children = {}
            self.suffix_link = None
            self.start = None
            self.end = None
            self.suffix_index = None

    def __init__(self, text):
        self.text = text
        self.root = self.Node()
        self.active_node = self.root
        self.active_edge = -1
        self.active_length = 0
        
        for i in range(len(text)):
            self._extend(i)

    def _extend(self, pos):
        # Ukkonen's algorithm implementation
        # Implementation details omitted for brevity
        pass

class SegmentTree:
    def __init__(self, arr):
        self.n = len(arr)
        self.tree = [0] * (4 * self.n)
        if self.n > 0:
            self._build(arr, 0, 0, self.n - 1)

    def _build(self, arr, node, start, end):
        if start == end:
            self.tree[node] = arr[start]
            return
        
        mid = (start + end) // 2
        self._build(arr, 2 * node + 1, start, mid)
        self._build(arr, 2 * node + 2, mid + 1, end)
        self.tree[node] = self.tree[2 * node + 1] + self.tree[2 * node + 2]

    def query(self, left: int, right: int) -> int:
        return self._query(0, 0, self.n - 1, left, right)

    def _query(self, node, start, end, left, right):
        if left > end or right < start:
            return 0
        if left <= start and right >= end:
            return self.tree[node]
        
        mid = (start + end) // 2
        return self._query(2 * node + 1, start, mid, left, right) + \
               self._query(2 * node + 2, mid + 1, end, left, right)

class FenwickTree:
    def __init__(self, n):
        self.size = n
        self.tree = [0] * (n + 1)

    def update(self, idx: int, delta: int):
        idx += 1
        while idx <= self.size:
            self.tree[idx] += delta
            idx += idx & (-idx)

    def prefix_sum(self, idx: int) -> int:
        idx += 1
        total = 0
        while idx > 0:
            total += self.tree[idx]
            idx -= idx & (-idx)
        return total

    def range_sum(self, left: int, right: int) -> int:
        return self.prefix_sum(right) - self.prefix_sum(left - 1)

class KDTree:
    class Node:
        def __init__(self, point, dim):
            self.point = point
            self.dim = dim
            self.left = None
            self.right = None

    def __init__(self, points):
        def build(points, depth):
            if not points:
                return None
                
            k = len(points[0])
            axis = depth % k
            
            points.sort(key=lambda x: x[axis])
            median = len(points) // 2
            
            node = self.Node(points[median], axis)
            node.left = build(points[:median], depth + 1)
            node.right = build(points[median + 1:], depth + 1)
            return node
            
        self.root = build(points, 0)

    def nearest_neighbor(self, target):
        best = [float('inf'), None]
        
        def search(node, depth):
            if not node:
                return
                
            point = node.point
            dist = sum((a - b) ** 2 for a, b in zip(point, target))
            
            if dist < best[0]:
                best[0] = dist
                best[1] = point
                
            axis = depth % len(target)
            diff = target[axis] - point[axis]
            
            if diff <= 0:
                close, far = node.left, node.right
            else:
                close, far = node.right, node.left
                
            search(close, depth + 1)
            if diff ** 2 < best[0]:
                search(far, depth + 1)
                
        search(self.root, 0)
        return best[1]

class MerkleTree:
    def __init__(self, data):
        self.leaves = [self._hash(item) for item in data]
        self.tree = self._build_tree(self.leaves)

    def _hash(self, data):
        # Simple hash function for demonstration
        return hash(str(data))

    def _build_tree(self, leaves):
        if len(leaves) == 1:
            return leaves[0]
            
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])
            
        next_level = []
        for i in range(0, len(leaves), 2):
            combined = self._hash(str(leaves[i]) + str(leaves[i + 1]))
            next_level.append(combined)
            
        return self._build_tree(next_level)

    def get_root(self):
        return self.tree

class QuadTree:
    class Node:
        def __init__(self, boundary):
            self.boundary = boundary  # (x, y, width, height)
            self.points = []
            self.children = [None] * 4  # NW, NE, SW, SE
            self.divided = False

    def __init__(self, boundary):
        self.root = self.Node(boundary)
        self.capacity = 4

    def insert(self, point):
        def _insert(node, point):
            if not self._in_boundary(node.boundary, point):
                return False
                
            if len(node.points) < self.capacity and not node.divided:
                node.points.append(point)
                return True
                
            if not node.divided:
                self._subdivide(node)
                
            return (_insert(node.children[0], point) or
                    _insert(node.children[1], point) or
                    _insert(node.children[2], point) or
                    _insert(node.children[3], point))
                    
        return _insert(self.root, point)

    def _in_boundary(self, boundary, point):
        x, y, w, h = boundary
        px, py = point
        return (x <= px <= x + w and
                y <= py <= y + h)

    def _subdivide(self, node):
        x, y, w, h = node.boundary
        
        nw = (x, y + h/2, w/2, h/2)
        ne = (x + w/2, y + h/2, w/2, h/2)
        sw = (x, y, w/2, h/2)
        se = (x + w/2, y, w/2, h/2)
        
        node.children[0] = self.Node(nw)
        node.children[1] = self.Node(ne)
        node.children[2] = self.Node(sw)
        node.children[3] = self.Node(se)
        
        node.divided = True

class UBTree:
    def __init__(self):
        self.root = None
        # UB-tree combines B-tree structure with Z-order curve
        # Implementation details omitted for brevity

class MTree:
    class Node:
        def __init__(self):
            self.routing_object = None
            self.covering_radius = 0
            self.children = []
            self.parent = None

    def __init__(self, distance_fn):
        self.root = self.Node()
        self.distance_fn = distance_fn