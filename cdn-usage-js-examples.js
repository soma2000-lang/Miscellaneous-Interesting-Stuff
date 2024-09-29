// 1. CDN Integration for Static Assets
// In your HTML file:
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CDN Example</title>
    <link rel="stylesheet" href="https://cdn.example.com/styles/main.min.css">
</head>
<body>
    <!-- Your content here -->
    <script src="https://cdn.example.com/scripts/app.min.js"></script>
</body>
</html>

// 2. Dynamic CDN URL Generation
// server.js
const express = require('express');
const app = express();

const CDN_URL = process.env.CDN_URL || 'https://cdn.example.com';
const ASSET_VERSION = process.env.ASSET_VERSION || '1.0.0';

app.get('/', (req, res) => {
    res.render('index', {
        cdnUrl: CDN_URL,
        assetVersion: ASSET_VERSION
    });
});

// In your template engine (e.g., EJS):
<link rel="stylesheet" href="<%= cdnUrl %>/styles/main.min.css?v=<%= assetVersion %>">

// 3. Image Optimization with Responsive Images
<picture>
    <source srcset="https://cdn.example.com/images/hero-large.webp" media="(min-width: 1200px)">
    <source srcset="https://cdn.example.com/images/hero-medium.webp" media="(min-width: 800px)">
    <img src="https://cdn.example.com/images/hero-small.webp" alt="Hero Image">
</picture>

// 4. Implementing Cache Busting
// webpack.config.js
const webpack = require('webpack');
const { WebpackManifestPlugin } = require('webpack-manifest-plugin');

module.exports = {
    // ... other webpack configurations
    output: {
        filename: '[name].[contenthash].js',
        path: path.resolve(__dirname, 'dist'),
    },
    plugins: [
        new WebpackManifestPlugin(),
    ],
};

// server.js
const manifest = require('./dist/manifest.json');

app.get('/', (req, res) => {
    res.render('index', { 
        scriptUrl: CDN_URL + manifest['main.js'],
        styleUrl: CDN_URL + manifest['main.css']
    });
});

// 5. Implementing a Multi-CDN Strategy
// cdn-manager.js
const CDNs = [
    { url: 'https://cdn1.example.com', weight: 0.6 },
    { url: 'https://cdn2.example.com', weight: 0.3 },
    { url: 'https://cdn3.example.com', weight: 0.1 }
];

function selectCDN() {
    const random = Math.random();
    let weightSum = 0;
    for (const cdn of CDNs) {
        weightSum += cdn.weight;
        if (random <= weightSum) {
            return cdn.url;
        }
    }
    return CDNs[0].url; // Fallback to first CDN
}

module.exports = { selectCDN };

// Usage in server.js
const { selectCDN } = require('./cdn-manager');

app.get('/', (req, res) => {
    const cdnUrl = selectCDN();
    res.render('index', { cdnUrl });
});

// 6. Implementing Edge Side Includes (ESI)
// Assuming your CDN supports ESI

// In your HTML template:
<html>
    <body>
        <h1>Welcome to our site</h1>
        <esi:include src="/api/user-info" />
        <esi:include src="/api/product-recommendations" />
    </body>
</html>

// server.js
app.get('/api/user-info', (req, res) => {
    res.set('Cache-Control', 'public, max-age=0, s-maxage=3600');
    // Generate and send user info
});

app.get('/api/product-recommendations', (req, res) => {
    res.set('Cache-Control', 'public, max-age=0, s-maxage=300');
    // Generate and send product recommendations
});

// 7. Implementing a Fallback Mechanism
// cdn-fallback.js
const axios = require('axios');

async function fetchWithFallback(url, fallbackUrls) {
    try {
        const response = await axios.get(url);
        return response.data;
    } catch (error) {
        if (fallbackUrls.length > 0) {
            console.warn(`Failed to fetch from ${url}, trying fallback`);
            return fetchWithFallback(fallbackUrls[0], fallbackUrls.slice(1));
        }
        throw error;
    }
}

// Usage
const primaryCdnUrl = 'https://cdn1.example.com/asset.js';
const fallbackUrls = [
    'https://cdn2.example.com/asset.js',
    'https://origin.example.com/asset.js'
];

fetchWithFallback(primaryCdnUrl, fallbackUrls)
    .then(data => console.log('Asset loaded successfully'))
    .catch(error => console.error('All CDNs failed', error));

// 8. Implementing Real User Monitoring (RUM)
// rum.js
function sendMetrics(metric) {
    navigator.sendBeacon('/analytics', JSON.stringify(metric));
}

// Measure and report Core Web Vitals
new PerformanceObserver((entryList) => {
    for (const entry of entryList.getEntries()) {
        if (entry.name === 'LCP') {
            sendMetrics({ lcp: entry.startTime });
        }
        if (entry.name === 'FID') {
            sendMetrics({ fid: entry.processingStart - entry.startTime });
        }
        if (entry.name === 'CLS') {
            sendMetrics({ cls: entry.value });
        }
    }
}).observe({ type: 'largest-contentful-paint', buffered: true });

// server.js
app.post('/analytics', express.json(), (req, res) => {
    // Process and store the metrics
    console.log('Received metrics:', req.body);
    res.sendStatus(204);
});

// 9. Implementing Token-Based Authentication for Protected Content
const jwt = require('jsonwebtoken');

function generateCDNToken(fileId, expiresIn = '1h') {
    return jwt.sign({ fileId }, process.env.CDN_SECRET, { expiresIn });
}

app.get('/protected-file/:id', (req, res) => {
    const fileId = req.params.id;
    const token = generateCDNToken(fileId);
    const cdnUrl = `https://cdn.example.com/files/${fileId}?token=${token}`;
    res.redirect(cdnUrl);
});

// On the CDN side (pseudo-code, as implementation depends on CDN provider):
function validateToken(token, fileId) {
    try {
        const decoded = jwt.verify(token, CDN_SECRET);
        return decoded.fileId === fileId;
    } catch (error) {
        return false;
    }
}

// 10. Implementing API Caching with CDN
app.get('/api/products', (req, res) => {
    res.set('Cache-Control', 'public, max-age=60, s-maxage=3600');
    res.set('Surrogate-Control', 'max-age=3600');
    // Fetch and send product data
});

// For dynamic content that shouldn't be cached:
app.get('/api/user-specific-data', (req, res) => {
    res.set('Cache-Control', 'no-store');
    // Fetch and send user-specific data
});
