class Node {
    constructor(isLeaf = false) {
        this.keys = [];
        this.children = [];
        this.isLeaf = isLeaf;
        this.next = null; // For leaf node linking
    }
}

class BPlusTree {
    constructor(order = 3) {
        this.root = new Node(true);
        this.order = order; // Maximum number of children per node
    }

    search(key) {
        let current = this.root;
        
        while (!current.isLeaf) {
            let i = 0;
            while (i < current.keys.length && key >= current.keys[i]) {
                i++;
            }
            current = current.children[i];
        }
        
        for (let i = 0; i < current.keys.length; i++) {
            if (current.keys[i] === key) {
                return true;
            }
        }
        return false;
    }

    insert(key) {
        let root = this.root;

        // If root is full, create new root
        if (root.keys.length === (this.order - 1)) {
            let newRoot = new Node(false);
            newRoot.children.push(this.root);
            this.root = newRoot;
            this.splitChild(newRoot, 0);
        }

        this.insertNonFull(this.root, key);
    }

    insertNonFull(node, key) {
        let i = node.keys.length - 1;

        if (node.isLeaf) {
            // Insert key in correct position
            while (i >= 0 && node.keys[i] > key) {
                node.keys[i + 1] = node.keys[i];
                i--;
            }
            node.keys[i + 1] = key;
        } else {
            // Find child which will have the new key
            while (i >= 0 && node.keys[i] > key) {
                i--;
            }
            i++;

            // If child is full, split it
            if (node.children[i].keys.length === (this.order - 1)) {
                this.splitChild(node, i);
                if (key > node.keys[i]) {
                    i++;
                }
            }
            this.insertNonFull(node.children[i], key);
        }
    }

    splitChild(parentNode, childIndex) {
        let child = parentNode.children[childIndex];
        let newNode = new Node(child.isLeaf);
        
        // Move half the keys to the new node
        let mid = Math.floor((this.order - 1) / 2);
        
        for (let i = 0; i < mid; i++) {
            newNode.keys.push(child.keys.pop());
            if (!child.isLeaf) {
                newNode.children.unshift(child.children.pop());
            }
        }

        if (!child.isLeaf) {
            newNode.children.unshift(child.children.pop());
        }

        // If these are leaf nodes, set up the leaf node chain
        if (child.isLeaf) {
            newNode.next = child.next;
            child.next = newNode;
        }

        // Insert new key into parent
        let insertIndex = parentNode.keys.length;
        while (insertIndex > childIndex && parentNode.keys[insertIndex - 1] > child.keys[mid - 1]) {
            parentNode.keys[insertIndex] = parentNode.keys[insertIndex - 1];
            parentNode.children[insertIndex + 1] = parentNode.children[insertIndex];
            insertIndex--;
        }

        parentNode.keys[insertIndex] = child.keys[mid - 1];
        parentNode.children[insertIndex + 1] = newNode;
    }

    // Helper method to print the tree (for debugging)
    print() {
        this.printNode(this.root, "");
    }

    printNode(node, prefix) {
        console.log(prefix + "Keys:", node.keys);
        if (!node.isLeaf) {
            for (let child of node.children) {
                this.printNode(child, prefix + "  ");
            }
        }
    }
}

// Example usage:
const tree = new BPlusTree(3);
tree.insert(10);
tree.insert(20);
tree.insert(5);
tree.insert(15);
tree.insert(25);

console.log("Search 15:", tree.search(15)); // true
console.log("Search 30:", tree.search(30)); // false

tree.print();
