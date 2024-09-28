const Redis = require('ioredis');
const { Producer, Consumer } = require('kafka-node');
const express = require('express');

// Initialize Redis for rate limiting
const redis = new Redis();

// Initialize Kafka
const kafkaClient = new kafka.KafkaClient({ kafkaHost: 'localhost:9092' });
const producer = new Producer(kafkaClient);
const consumer = new Consumer(kafkaClient, [{ topic: 'tasks' }]);

// Initialize Express
const app = express();
app.use(express.json());

// Rate limiter configuration
const RATE_LIMIT_WINDOW = 60; // 1 minute
const DEFAULT_RATE_LIMIT = 1000; // 1000 requests per minute

// Function to get rate limit for an account
async function getAccountRateLimit(accountId) {
  const limit = await redis.get(`rate_limit:${accountId}`);
  return limit ? parseInt(limit) : DEFAULT_RATE_LIMIT;
}

// Middleware for rate limiting
async function rateLimitMiddleware(req, res, next) {
  const accountId = req.headers['x-account-id'];
  if (!accountId) {
    return res.status(400).json({ error: 'Account ID is required' });
  }

  const rateLimit = await getAccountRateLimit(accountId);
  const currentCount = await redis.incr(`count:${accountId}`);
  
  if (currentCount === 1) {
    await redis.expire(`count:${accountId}`, RATE_LIMIT_WINDOW);
  }

  if (currentCount > rateLimit) {
    return res.status(429).json({ error: 'Rate limit exceeded' });
  }

  next();
}

// API to enqueue a task
app.post('/enqueue', rateLimitMiddleware, (req, res) => {
  const { task } = req.body;
  const accountId = req.headers['x-account-id'];

  producer.send([{ topic: 'tasks', messages: JSON.stringify({ accountId, task }) }], (err) => {
    if (err) {
      res.status(500).json({ error: 'Failed to enqueue task' });
    } else {
      res.status(200).json({ message: 'Task enqueued successfully' });
    }
  });
});

// API to update rate limit for an account
app.post('/set-rate-limit', async (req, res) => {
  const { accountId, limit } = req.body;
  await redis.set(`rate_limit:${accountId}`, limit);
  res.status(200).json({ message: 'Rate limit updated successfully' });
});

// Function to process tasks with rate limiting
async function processTask(task) {
  const { accountId, task: taskData } = JSON.parse(task.value);
  const rateLimit = await getAccountRateLimit(accountId);
  
  const currentCount = await redis.incr(`exec_count:${accountId}`);
  if (currentCount === 1) {
    await redis.expire(`exec_count:${accountId}`, RATE_LIMIT_WINDOW);
  }

  if (currentCount <= rateLimit) {
    // Process the task
    console.log(`Processing task for account ${accountId}:`, taskData);
    // Add your task processing logic here
  } else {
    // Requeue the task
    producer.send([{ topic: 'tasks', messages: task.value }], (err) => {
      if (err) console.error('Failed to requeue task:', err);
    });
  }
}

// Consume tasks from Kafka
consumer.on('message', processTask);

// Start the server
const PORT = 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));

// Error handling
producer.on('error', console.error);
consumer.on('error', console.error);
