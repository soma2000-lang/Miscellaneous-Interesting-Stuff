// main.js
const { Worker } = require('worker_threads');
const os = require('os');
const express = require('express');

const app = express();
const port = 3000;

// Create a worker pool
const numCPUs = os.cpus().length;
const workers = new Set();

for (let i = 0; i < numCPUs; i++) {
    const worker = new Worker('./worker.js');
    workers.add(worker);

    worker.on('message', (result) => {
        console.log(`Worker result: ${result}`);
    });

    worker.on('error', (error) => {
        console.error(`Worker error: ${error}`);
    });

    worker.on('exit', (code) => {
        console.log(`Worker exited with code ${code}`);
        workers.delete(worker);
        
        // Restart the worker if it crashes
        if (code !== 0) {
            const newWorker = new Worker('./worker.js');
            workers.add(newWorker);
        }
    });
}

// Function to get an available worker
function getWorker() {
    return new Promise((resolve) => {
        const checkWorker = () => {
            for (const worker of workers) {
                if (worker.threadId % 2 === 0) {  // Simple load balancing
                    return resolve(worker);
                }
            }
            setImmediate(checkWorker);
        };
        checkWorker();
    });
}

// API endpoint that uses a worker
app.get('/compute/:number', async (req, res) => {
    const number = parseInt(req.params.number);
    const worker = await getWorker();
    
    worker.postMessage({ action: 'fibonacci', number });
    
    worker.once('message', (result) => {
        res.json({ result });
    });
});

// API endpoint for a simple task
app.get('/hello', (req, res) => {
    res.json({ message: 'Hello, World!' });
});

app.listen(port, () => {
    console.log(`Server running on port ${port}`);
});

// worker.js
const { parentPort } = require('worker_threads');

function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

parentPort.on('message', (message) => {
    if (message.action === 'fibonacci') {
        const result = fibonacci(message.number);
        parentPort.postMessage(result);
    }
});

// Example of using worker threads for database operations
// db-worker.js
const { parentPort } = require('worker_threads');
const { MongoClient } = require('mongodb');

const url = 'mongodb://localhost:27017';
const dbName = 'myproject';

let db;

async function connectDB() {
    const client = new MongoClient(url);
    await client.connect();
    db = client.db(dbName);
    console.log("Connected to database");
}

connectDB().catch(console.error);

parentPort.on('message', async (message) => {
    if (!db) {
        parentPort.postMessage({ error: 'Database not connected' });
        return;
    }

    switch (message.action) {
        case 'find':
            try {
                const result = await db.collection(message.collection).find(message.query).toArray();
                parentPort.postMessage({ result });
            } catch (error) {
                parentPort.postMessage({ error: error.message });
            }
            break;
        case 'insert':
            try {
                const result = await db.collection(message.collection).insertOne(message.document);
                parentPort.postMessage({ result });
            } catch (error) {
                parentPort.postMessage({ error: error.message });
            }
            break;
        default:
            parentPort.postMessage({ error: 'Unknown action' });
    }
});

// Using the DB worker in main.js
const dbWorker = new Worker('./db-worker.js');

app.get('/users', (req, res) => {
    dbWorker.postMessage({ action: 'find', collection: 'users', query: {} });
    dbWorker.once('message', (result) => {
        if (result.error) {
            res.status(500).json({ error: result.error });
        } else {
            res.json(result.result);
        }
    });
});

app.post('/users', express.json(), (req, res) => {
    dbWorker.postMessage({ action: 'insert', collection: 'users', document: req.body });
    dbWorker.once('message', (result) => {
        if (result.error) {
            res.status(500).json({ error: result.error });
        } else {
            res.json(result.result);
        }
    });
});

// Example of using worker threads for file processing
// file-worker.js
const { parentPort } = require('worker_threads');
const fs = require('fs').promises;
const path = require('path');

parentPort.on('message', async (message) => {
    if (message.action === 'processFile') {
        try {
            const content = await fs.readFile(message.filePath, 'utf8');
            const lines = content.split('\n').length;
            const size = (await fs.stat(message.filePath)).size;
            
            parentPort.postMessage({
                fileName: path.basename(message.filePath),
                lines,
                size
            });
        } catch (error) {
            parentPort.postMessage({ error: error.message });
        }
    }
});

// Using the file worker in main.js
const fileWorker = new Worker('./file-worker.js');

app.get('/file-info', (req, res) => {
    const filePath = req.query.path;
    if (!filePath) {
        return res.status(400).json({ error: 'File path is required' });
    }

    fileWorker.postMessage({ action: 'processFile', filePath });
    fileWorker.once('message', (result) => {
        if (result.error) {
            res.status(500).json({ error: result.error });
        } else {
            res.json(result);
        }
    });
});
