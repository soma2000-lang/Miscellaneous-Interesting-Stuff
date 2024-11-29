class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

class AVLTree:
    def getHeight(self, node):
        if not node:
            return 0
        return node.height
    
    def getBalance(self, node):
        if not node:
            return 0
        return self.getHeight(node.left) - self.getHeight(node.right)
    
    def rightRotate(self, y):
        x = y.left
        T2 = x.right
        x.right = y
        y.left = T2
        y.height = max(self.getHeight(y.left), self.getHeight(y.right)) + 1
        x.height = max(self.getHeight(x.left), self.getHeight(x.right)) + 1
        return x
    
    def leftRotate(self, x):
        y = x.right
        T2 = y.left
        y.left = x
        x.right = T2
        x.height = max(self.getHeight(x.left), self.getHeight(x.right)) + 1
        y.height = max(self.getHeight(y.left), self.getHeight(y.right)) + 1
        return y
    
    def insert(self, root, key):
        if not root:
            return Node(key)
            
        if key < root.key:
            root.left = self.insert(root.left, key)
        elif key > root.key:
            root.right = self.insert(root.right, key)
        else:
            return root
        
        root.height = max(self.getHeight(root.left), self.getHeight(root.right)) + 1
        balance = self.getBalance(root)
        
        # Left Left
        if balance > 1 and key < root.left.key:
            return self.rightRotate(root)
        
        # Right Right
        if balance < -1 and key > root.right.key:
            return self.leftRotate(root)
        
        # Left Right
        if balance > 1 and key > root.left.key:
            root.left = self.leftRotate(root.left)
            return self.rightRotate(root)
        
        # Right Left
        if balance < -1 and key < root.right.key:
            root.right = self.rightRotate(root.right)
            return self.leftRotate(root)
        
        return root
    
    def delete(self, root, key):
        if not root:
            return root
            
        if key < root.key:
            root.left = self.delete(root.left, key)
        elif key > root.key:
            root.right = self.delete(root.right, key)
        else:
            if not root.left:
                return root.right
            elif not root.right:
                return root.left
            temp = self.getMinValueNode(root.right)
            root.key = temp.key
            root.right = self.delete(root.right, temp.key)
            
        if not root:
            return root
            
        root.height = max(self.getHeight(root.left), self.getHeight(root.right)) + 1
        balance = self.getBalance(root)
        
        # Left Left
        if balance > 1 and self.getBalance(root.left) >= 0:
            return self.rightRotate(root)
        
        # Right Right
        if balance < -1 and self.getBalance(root.right) <= 0:
            return self.leftRotate(root)
        
        # Left Right
        if balance > 1 and self.getBalance(root.left) < 0:
            root.left = self.leftRotate(root.left)
            return self.rightRotate(root)
        
        # Right Left
        if balance < -1 and self.getBalance(root.right) > 0:
            root.right = self.rightRotate(root.right)
            return self.leftRotate(root)
            
        return root
        
    def getMinValueNode(self, root):
        current = root
        while current.left:
            current = current.left
        return current

    def inorderTraversal(self, root):
        if not root:
            return []
        return self.inorderTraversal(root.left) + [root.key] + self.inorderTraversal(root.right)
