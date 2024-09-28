const admin = require('firebase-admin');
const { MongoClient } = require('mongodb');
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');
const os = require('os');

// Initialize Firebase Admin SDK
admin.initializeApp({
  credential: admin.credential.applicationDefault(),
  databaseURL: 'https://your-project-id.firebaseio.com'
});

// MongoDB connection string
const mongoUri = 'mongodb://localhost:27017/your_database';

// Number of worker threads (adjust based on your server's capabilities)
const numWorkers = os.cpus().length;

if (isMainThread) {
  // Main thread code
  async function main() {
    const mongoClient = new MongoClient(mongoUri);
    await mongoClient.connect();
    const db = mongoClient.db();

    // Create a collection for tracking sync status
    const syncStatusCollection = db.collection('sync_status');

    // Initialize worker threads
    const workers = [];
    for (let i = 0; i < numWorkers; i++) {
      workers.push(new Worker(__filename, { workerData: { workerId: i } }));
    }

    // Listen for Firestore changes
    const firestore = admin.firestore();
    const query = firestore.collectionGroup('events').where('timestamp', '>=', admin.firestore.Timestamp.now());
    
    query.onSnapshot((snapshot) => {
      snapshot.docChanges().forEach((change) => {
        const data = change.doc.data();
        const workerId = Math.floor(Math.random() * numWorkers);
        workers[workerId].postMessage({ type: 'sync', data });
      });
    });

    // Handle messages from workers
    workers.forEach((worker, index) => {
      worker.on('message', async (message) => {
        if (message.type === 'syncComplete') {
          await syncStatusCollection.updateOne(
            { _id: message.data._id },
            { $set: { synced: true, syncTime: new Date() } },
            { upsert: true }
          );
        }
      });
    });
  }

  main().catch(console.error);
} else {
  // Worker thread code
  const mongoClient = new MongoClient(mongoUri);

  async function syncToMongoDB(data) {
    await mongoClient.connect();
    const db = mongoClient.db();
    const collection = db.collection('events');

    const startTime = process.hrtime();

    await collection.updateOne(
      { _id: data.id },
      { $set: data },
      { upsert: true }
    );

    const [seconds, nanoseconds] = process.hrtime(startTime);
    const latency = seconds * 1000 + nanoseconds / 1e6;

    parentPort.postMessage({
      type: 'syncComplete',
      data: { _id: data.id, latency }
    });
  }

  parentPort.on('message', (message) => {
    if (message.type === 'sync') {
      syncToMongoDB(message.data).catch(console.error);
    }
  });
}
