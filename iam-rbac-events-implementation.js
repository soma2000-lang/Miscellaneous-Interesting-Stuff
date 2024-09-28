// File: server.js
const express = require('express');
const { Pool } = require('pg');
const Redis = require('ioredis');
const { Kafka } = require('kafkajs');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');

const app = express();
app.use(express.json());

// Database setup
const pool = new Pool({
  user: 'your_username',
  host: 'localhost',
  database: 'iam_db',
  password: 'your_password',
  port: 5432,
});

// Redis setup
const redis = new Redis();

// Kafka setup
const kafka = new Kafka({
  clientId: 'iam-service',
  brokers: ['localhost:9092'],
});
const producer = kafka.producer();
const consumer = kafka.consumer({ groupId: 'iam-group' });

// JWT secret (use a secure, environment-specific secret in production)
const JWT_SECRET = 'your_jwt_secret';

// Authentication
async function authenticate(username, password) {
  const result = await pool.query('SELECT * FROM users WHERE username = $1', [username]);
  if (result.rows.length > 0) {
    const user = result.rows[0];
    if (await bcrypt.compare(password, user.password_hash)) {
      return user;
    }
  }
  return null;
}

// RBAC
async function checkPermission(userId, resource, action) {
  const result = await pool.query(`
    SELECT 1 FROM users u
    JOIN user_roles ur ON u.id = ur.user_id
    JOIN roles r ON ur.role_id = r.id
    JOIN role_permissions rp ON r.id = rp.role_id
    JOIN permissions p ON rp.permission_id = p.id
    WHERE u.id = $1 AND p.resource = $2 AND p.action = $3
  `, [userId, resource, action]);
  return result.rows.length > 0;
}

// Maker-Checker Pattern
async function createPendingAction(makerId, action, data) {
  return pool.query('INSERT INTO pending_actions (maker_id, action, data) VALUES ($1, $2, $3) RETURNING id', 
    [makerId, action, JSON.stringify(data)]);
}

async function approvePendingAction(checkerId, actionId) {
  const result = await pool.query('SELECT * FROM pending_actions WHERE id = $1', [actionId]);
  if (result.rows.length > 0) {
    const action = result.rows[0];
    // Implement your approval logic here
    await pool.query('DELETE FROM pending_actions WHERE id = $1', [actionId]);
    return true;
  }
  return false;
}

// Event Publishing
async function publishEvent(topic, event) {
  await producer.connect();
  await producer.send({
    topic,
    messages: [{ value: JSON.stringify(event) }],
  });
  await producer.disconnect();
}

// Middleware
function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (token == null) return res.sendStatus(401);

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) return res.sendStatus(403);
    req.user = user;
    next();
  });
}

// Routes
app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  const user = await authenticate(username, password);
  if (user) {
    const token = jwt.sign({ id: user.id, username: user.username }, JWT_SECRET, { expiresIn: '1h' });
    res.json({ token });
  } else {
    res.status(400).send('Invalid credentials');
  }
});

app.post('/action', authenticateToken, async (req, res) => {
  const { resource, action, data } = req.body;
  if (await checkPermission(req.user.id, resource, action)) {
    const result = await createPendingAction(req.user.id, action, data);
    res.json({ pendingActionId: result.rows[0].id });
  } else {
    res.status(403).send('Permission denied');
  }
});

app.post('/approve', authenticateToken, async (req, res) => {
  const { actionId } = req.body;
  if (await approvePendingAction(req.user.id, actionId)) {
    res.send('Action approved');
  } else {
    res.status(400).send('Invalid action or already approved');
  }
});

app.post('/event', authenticateToken, async (req, res) => {
  const { topic, event } = req.body;
  await publishEvent(topic, event);
  res.send('Event published');
});

// Event Consumption
async function setupConsumer() {
  await consumer.connect();
  await consumer.subscribe({ topic: 'iam-events', fromBeginning: true });
  await consumer.run({
    eachMessage: async ({ topic, partition, message }) => {
      console.log({
        value: message.value.toString(),
      });
      // Process the event here
    },
  });
}

// Start the server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  setupConsumer().catch(console.error);
});

// Database setup script (run this separately to set up your database)
async function setupDatabase() {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(100) NOT NULL
      );

      CREATE TABLE IF NOT EXISTS roles (
        id SERIAL PRIMARY KEY,
        name VARCHAR(50) UNIQUE NOT NULL
      );

      CREATE TABLE IF NOT EXISTS permissions (
        id SERIAL PRIMARY KEY,
        resource VARCHAR(50) NOT NULL,
        action VARCHAR(50) NOT NULL,
        UNIQUE (resource, action)
      );

      CREATE TABLE IF NOT EXISTS user_roles (
        user_id INTEGER REFERENCES users(id),
        role_id INTEGER REFERENCES roles(id),
        PRIMARY KEY (user_id, role_id)
      );

      CREATE TABLE IF NOT EXISTS role_permissions (
        role_id INTEGER REFERENCES roles(id),
        permission_id INTEGER REFERENCES permissions(id),
        PRIMARY KEY (role_id, permission_id)
      );

      CREATE TABLE IF NOT EXISTS pending_actions (
        id SERIAL PRIMARY KEY,
        maker_id INTEGER REFERENCES users(id),
        action VARCHAR(50) NOT NULL,
        data JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `);
    console.log('Database setup complete');
  } catch (err) {
    console.error('Error setting up database', err);
  } finally {
    client.release();
  }
}

setupDatabase().catch(console.error);
