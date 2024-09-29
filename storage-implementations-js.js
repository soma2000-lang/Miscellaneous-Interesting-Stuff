// File Storage Implementation

const fs = require('fs').promises;
const path = require('path');
const crypto = require('crypto');

class FileStorage {
    constructor(rootDir) {
        this.rootDir = rootDir;
    }

    async createDirectory(dirPath) {
        const fullPath = path.join(this.rootDir, dirPath);
        await fs.mkdir(fullPath, { recursive: true });
    }

    async writeFile(filePath, content) {
        const fullPath = path.join(this.rootDir, filePath);
        await fs.writeFile(fullPath, content);
    }

    async readFile(filePath) {
        const fullPath = path.join(this.rootDir, filePath);
        return await fs.readFile(fullPath, 'utf8');
    }

    async deleteFile(filePath) {
        const fullPath = path.join(this.rootDir, filePath);
        await fs.unlink(fullPath);
    }

    async listFiles(dirPath) {
        const fullPath = path.join(this.rootDir, dirPath);
        return await fs.readdir(fullPath);
    }

    async moveFile(oldPath, newPath) {
        const fullOldPath = path.join(this.rootDir, oldPath);
        const fullNewPath = path.join(this.rootDir, newPath);
        await fs.rename(fullOldPath, fullNewPath);
    }

    async getFileStats(filePath) {
        const fullPath = path.join(this.rootDir, filePath);
        return await fs.stat(fullPath);
    }

    async searchFiles(dirPath, searchTerm) {
        const fullPath = path.join(this.rootDir, dirPath);
        const files = await fs.readdir(fullPath, { withFileTypes: true });
        const results = [];

        for (const file of files) {
            if (file.isDirectory()) {
                results.push(...await this.searchFiles(path.join(dirPath, file.name), searchTerm));
            } else if (file.name.includes(searchTerm)) {
                results.push(path.join(dirPath, file.name));
            }
        }

        return results;
    }
}

// Usage example for File Storage
async function fileStorageExample() {
    const storage = new FileStorage('./storage');

    await storage.createDirectory('documents');
    await storage.writeFile('documents/example.txt', 'Hello, World!');
    const content = await storage.readFile('documents/example.txt');
    console.log('File content:', content);

    const files = await storage.listFiles('documents');
    console.log('Files in documents:', files);

    await storage.moveFile('documents/example.txt', 'documents/moved_example.txt');
    const stats = await storage.getFileStats('documents/moved_example.txt');
    console.log('File stats:', stats);

    const searchResults = await storage.searchFiles('documents', 'example');
    console.log('Search results:', searchResults);

    await storage.deleteFile('documents/moved_example.txt');
}

// Object Storage Implementation

class ObjectStorage {
    constructor() {
        this.storage = new Map();
    }

    generateKey() {
        return crypto.randomBytes(16).toString('hex');
    }

    put(data, metadata = {}) {
        const key = this.generateKey();
        const timestamp = new Date().toISOString();
        this.storage.set(key, {
            data,
            metadata: { ...metadata, createdAt: timestamp, updatedAt: timestamp },
        });
        return key;
    }

    get(key) {
        return this.storage.get(key);
    }

    delete(key) {
        return this.storage.delete(key);
    }

    update(key, data, metadata = {}) {
        if (!this.storage.has(key)) {
            throw new Error('Object not found');
        }
        const existingObject = this.storage.get(key);
        const timestamp = new Date().toISOString();
        this.storage.set(key, {
            data,
            metadata: { 
                ...existingObject.metadata, 
                ...metadata, 
                updatedAt: timestamp 
            },
        });
    }

    list() {
        return Array.from(this.storage.entries()).map(([key, value]) => ({
            key,
            metadata: value.metadata,
        }));
    }

    search(query) {
        return Array.from(this.storage.entries())
            .filter(([key, value]) => 
                Object.entries(query).every(([k, v]) => 
                    value.metadata[k] && value.metadata[k].includes(v)
                )
            )
            .map(([key, value]) => ({
                key,
                metadata: value.metadata,
            }));
    }
}

// Usage example for Object Storage
async function objectStorageExample() {
    const storage = new ObjectStorage();

    // Put objects
    const key1 = storage.put('Hello, World!', { type: 'greeting', language: 'English' });
    const key2 = storage.put('Bonjour, le monde!', { type: 'greeting', language: 'French' });

    // Get object
    const obj1 = storage.get(key1);
    console.log('Object 1:', obj1);

    // Update object
    storage.update(key1, 'Hello, Updated World!', { status: 'updated' });
    const updatedObj1 = storage.get(key1);
    console.log('Updated Object 1:', updatedObj1);

    // List objects
    const allObjects = storage.list();
    console.log('All objects:', allObjects);

    // Search objects
    const searchResults = storage.search({ type: 'greeting', language: 'French' });
    console.log('Search results:', searchResults);

    // Delete object
    storage.delete(key2);
    console.log('After deletion:', storage.list());
}

// Run examples
fileStorageExample().catch(console.error);
objectStorageExample().catch(console.error);

// Example of integrating File and Object Storage

class HybridStorage {
    constructor(fileStorageRoot) {
        this.fileStorage = new FileStorage(fileStorageRoot);
        this.objectStorage = new ObjectStorage();
    }

    async storeFile(filePath, content, metadata = {}) {
        await this.fileStorage.writeFile(filePath, content);
        const key = this.objectStorage.put(filePath, {
            ...metadata,
            type: 'file',
            path: filePath,
        });
        return key;
    }

    async retrieveFile(key) {
        const obj = this.objectStorage.get(key);
        if (!obj || obj.metadata.type !== 'file') {
            throw new Error('Not a file or not found');
        }
        const content = await this.fileStorage.readFile(obj.metadata.path);
        return { content, metadata: obj.metadata };
    }

    storeObject(data, metadata = {}) {
        return this.objectStorage.put(data, { ...metadata, type: 'object' });
    }

    retrieveObject(key) {
        const obj = this.objectStorage.get(key);
        if (!obj || obj.metadata.type !== 'object') {
            throw new Error('Not an object or not found');
        }
        return obj;
    }

    async search(query) {
        const results = this.objectStorage.search(query);
        return Promise.all(results.map(async (result) => {
            if (result.metadata.type === 'file') {
                const content = await this.fileStorage.readFile(result.metadata.path);
                return { ...result, content };
            }
            return result;
        }));
    }
}

// Usage example for Hybrid Storage
async function hybridStorageExample() {
    const storage = new HybridStorage('./hybrid_storage');

    // Store a file
    const fileKey = await storage.storeFile('example.txt', 'Hello, Hybrid World!', { category: 'greeting' });

    // Store an object
    const objectKey = storage.storeObject({ message: 'Hello, Object!' }, { category: 'greeting' });

    // Retrieve file
    const file = await storage.retrieveFile(fileKey);
    console.log('Retrieved file:', file);

    // Retrieve object
    const object = storage.retrieveObject(objectKey);
    console.log('Retrieved object:', object);

    // Search
    const searchResults = await storage.search({ category: 'greeting' });
    console.log('Search results:', searchResults);
}

hybridStorageExample().catch(console.error);
