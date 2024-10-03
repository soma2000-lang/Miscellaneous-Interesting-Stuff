// app.js
const express = require('express');
const mongoose = require('mongoose');
const jwt = require('jsonwebtoken');
const { v4: uuidv4 } = require('uuid');
const app = express();

app.use(express.json());

// Connect to MongoDB
mongoose.connect('mongodb://localhost/logoexecutive', { useNewUrlParser: true, useUnifiedTopology: true });

// Guest Session Model
const GuestSessionSchema = new mongoose.Schema({
  token: { type: String, required: true, unique: true },
  expiresAt: { type: Date, required: true }
});

const GuestSession = mongoose.model('GuestSession', GuestSessionSchema);

// Middleware to verify JWT token
const verifyToken = (req, res, next) => {
  const token = req.headers['authorization'];
  if (!token) return res.status(403).send({ auth: false, message: 'No token provided.' });
  
  jwt.verify(token.split(' ')[1], process.env.JWT_SECRET, (err, decoded) => {
    if (err) return res.status(500).send({ auth: false, message: 'Failed to authenticate token.' });
    
    req.userId = decoded.id;
    req.isGuest = decoded.isGuest;
    next();
  });
};

// Guest sign-in endpoint
app.post('/api/auth/guest-signin', async (req, res) => {
  try {
    const guestToken = uuidv4();
    const expirationTime = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 hours from now

    const guestSession = new GuestSession({
      token: guestToken,
      expiresAt: expirationTime
    });

    await guestSession.save();

    const token = jwt.sign({ id: guestToken, isGuest: true }, process.env.JWT_SECRET, {
      expiresIn: 86400 // 24 hours
    });

    res.status(200).send({ auth: true, token: token });
  } catch (error) {
    res.status(500).send({ message: 'Error creating guest session' });
  }
});

// Protected endpoint example
app.get('/api/protected', verifyToken, async (req, res) => {
  if (req.isGuest) {
    // Check if the guest session is still valid
    const guestSession = await GuestSession.findOne({ token: req.userId });
    if (!guestSession || guestSession.expiresAt < new Date()) {
      return res.status(401).send({ message: 'Guest session has expired' });
    }
    return res.status(200).send({ message: 'Welcome, guest user! This is a limited view.' });
  } else {
    // Full functionality for registered users
    return res.status(200).send({ message: 'Welcome, registered user! You have full access.' });
  }
});

// Logout endpoint
app.post('/api/auth/logout', verifyToken, async (req, res) => {
  if (req.isGuest) {
    await GuestSession.deleteOne({ token: req.userId });
  }
  res.status(200).send({ auth: false, token: null });
});

// Start the server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});

// Cleanup job (run this periodically, e.g., using a cron job)
async function cleanupExpiredSessions() {
  try {
    await GuestSession.deleteMany({ expiresAt: { $lt: new Date() } });
    console.log('Expired guest sessions cleaned up');
  } catch (error) {
    console.error('Error cleaning up expired sessions:', error);
  }
}
