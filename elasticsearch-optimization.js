const { Client } = require('@elastic/elasticsearch');
const cluster = require('cluster');
const numCPUs = require('os').cpus().length;

// Elasticsearch client configuration
const client = new Client({
  node: 'http://localhost:9200',
  maxRetries: 5,
  requestTimeout: 60000,
  sniffOnStart: true
});

// Optimized index settings
const optimizedIndexSettings = {
  settings: {
    index: {
      number_of_shards: 10,
      number_of_replicas: 1,
      refresh_interval: '30s',
      translog: {
        durability: 'async',
        sync_interval: '30s'
      },
      routing: {
        allocation: {
          total_shards_per_node: 3
        }
      }
    }
  },
  mappings: {
    properties: {
      // Define your mappings here
      // Example:
      // id: { type: 'keyword' },
      // timestamp: { type: 'date' },
      // data: { type: 'text' }
    }
  }
};

// Bulk indexing function
async function bulkIndex(documents) {
  const body = documents.flatMap(doc => [
    { index: { _index: 'optimized_index' } },
    doc
  ]);

  const { body: bulkResponse } = await client.bulk({ refresh: false, body });

  if (bulkResponse.errors) {
    const erroredDocuments = [];
    bulkResponse.items.forEach((action, i) => {
      const operation = Object.keys(action)[0];
      if (action[operation].error) {
        erroredDocuments.push({
          status: action[operation].status,
          error: action[operation].error,
          operation: body[i * 2],
          document: body[i * 2 + 1]
        });
      }
    });
    console.error('Failed documents:', erroredDocuments);
  }
}

// Worker process
if (cluster.isWorker) {
  process.on('message', async (documents) => {
    try {
      await bulkIndex(documents);
      process.send('done');
    } catch (error) {
      console.error('Error in worker:', error);
      process.send('error');
    }
  });
}

// Master process
if (cluster.isMaster) {
  // Create optimized index
  async function createOptimizedIndex() {
    try {
      await client.indices.create({
        index: 'optimized_index',
        body: optimizedIndexSettings
      });
      console.log('Optimized index created successfully');
    } catch (error) {
      console.error('Error creating index:', error);
    }
  }

  // Simulate high-throughput indexing
  async function simulateHighThroughput() {
    const totalDocuments = 600000000; // 600M writes per month
    const batchSize = 10000;
    const workers = [];

    // Fork workers
    for (let i = 0; i < numCPUs; i++) {
      workers.push(cluster.fork());
    }

    let processedDocuments = 0;
    const startTime = Date.now();

    while (processedDocuments < totalDocuments) {
      const batch = Array.from({ length: batchSize }, () => ({
        timestamp: new Date(),
        data: 'Sample data'
      }));

      const availableWorker = workers.find(w => w.isIdle);
      if (availableWorker) {
        availableWorker.isIdle = false;
        availableWorker.send(batch);
        availableWorker.once('message', (msg) => {
          if (msg === 'done') {
            processedDocuments += batchSize;
            availableWorker.isIdle = true;
          }
        });
      }

      // Simple backpressure mechanism
      if (!workers.some(w => w.isIdle)) {
        await new Promise(resolve => setTimeout(resolve, 10));
      }
    }

    const endTime = Date.now();
    const totalTimeSeconds = (endTime - startTime) / 1000;
    console.log(`Processed ${totalDocuments} documents in ${totalTimeSeconds} seconds`);
    console.log(`Average throughput: ${totalDocuments / totalTimeSeconds} documents/second`);

    // Cleanup
    workers.forEach(worker => worker.kill());
    process.exit(0);
  }

  createOptimizedIndex().then(simulateHighThroughput);
}

// Additional optimizations:
// 1. Implement circuit breaker to prevent OOM errors
// 2. Use adaptive replica selection for better query distribution
// 3. Implement index lifecycle management for cost-effective data retention
// 4. Use force merge after bulk indexing to optimize segment merges
// 5. Implement custom routing for faster query performance
