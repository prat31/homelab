import express from 'express'
import fs from "fs";
import https from "https";
import http from "http";
import dns from "dns";
import {getBook} from './bookscraper.js'
import getAuthor from "./authorscraper.js";

const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15";

// Persistent cache for autocomplete results: bookId -> autocomplete item
const bookCache = new Map();
// Cache for author data: authorId -> author data
const authorCache = new Map();

// Load persistent cache from disk on startup
const CACHE_FILE = '/tmp/cache.json';
function loadCache() {
  try {
    if (fs.existsSync(CACHE_FILE)) {
      const data = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
      if (data.books) for (const [k, v] of Object.entries(data.books)) bookCache.set(k, v);
      if (data.authors) for (const [k, v] of Object.entries(data.authors)) authorCache.set(k, v);
      console.log(`Loaded ${bookCache.size} books, ${authorCache.size} authors from persistent cache`);
    }
  } catch (e) {
    console.error('Failed to load cache:', e.message);
  }
}

// Save cache to disk (throttled)
let saveTimer = null;
function saveCache() {
  if (saveTimer) return;
  saveTimer = setTimeout(() => {
    saveTimer = null;
    try {
      const data = {
        books: Object.fromEntries(bookCache),
        authors: Object.fromEntries(authorCache),
      };
      fs.writeFileSync(CACHE_FILE, JSON.stringify(data));
    } catch (e) {
      console.error('Failed to save cache:', e.message);
    }
  }, 5000);
}
loadCache();

// Resolve real Goodreads IP using public DNS (bypassing Docker DNS)
function resolveGoodreads() {
  return new Promise((resolve, reject) => {
    const resolver = new dns.Resolver();
    resolver.setServers(['8.8.8.8', '1.1.1.1']);
    resolver.resolve4('www.goodreads.com', (err, addresses) => {
      if (err || !addresses.length) reject(err || new Error('No IPs'));
      else resolve(addresses[0]);
    });
  });
}

// Proxy a request to the real Goodreads
async function proxyToGoodreads(req, res, path) {
  try {
    const ip = await resolveGoodreads();
    const url = new URL(path, 'https://www.goodreads.com');
    if (req.method === 'GET' && Object.keys(req.query || {}).length === 0) {
      // preserve query string from original request
      const origUrl = new URL(req.originalUrl || path, 'https://www.goodreads.com');
      url.search = origUrl.search;
    }

    const options = {
      hostname: ip,
      port: 443,
      path: url.pathname + url.search,
      method: req.method,
      headers: {
        'Host': 'www.goodreads.com',
        'User-Agent': UA,
        'Accept': req.headers['accept'] || '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
      },
      servername: 'www.goodreads.com',
    };

    const proxyReq = https.request(options, (proxyRes) => {
      const chunks = [];
      proxyRes.on('data', chunk => chunks.push(chunk));
      proxyRes.on('end', () => {
        const body = Buffer.concat(chunks).toString();
        const contentType = proxyRes.headers['content-type'] || 'application/json';

        // If this is an autocomplete request, cache the results
        if (path.includes('/book/auto_complete')) {
          try {
            const data = JSON.parse(body);
            if (Array.isArray(data)) {
              for (const item of data) {
                if (item.bookId) {
                  bookCache.set(String(item.bookId), item);
                  console.log(`Cached book ${item.bookId}: ${item.title?.substring(0, 40)}`);
                }
              }
              saveCache();
            }
          } catch (e) {
            console.error('Failed to cache autocomplete:', e.message);
          }
        }

        res.status(proxyRes.statusCode || 200);
        res.set('Content-Type', contentType);
        res.send(body);
      });
    });

    proxyReq.on('error', (e) => {
      console.error('Proxy error:', e.message);
      res.status(502).json({error: 'Proxy failed', detail: e.message});
    });

    proxyReq.end();
  } catch (e) {
    console.error('Proxy setup error:', e.message);
    res.status(502).json({error: 'Proxy failed', detail: e.message});
  }
}

// Build a bookinfo-format work resource from cached autocomplete data
function buildWorkFromCache(bookId) {
  const cached = bookCache.get(String(bookId));
  if (!cached) return null;

  const authorId = cached.author?.id || 0;
  let authorInfo = authorCache.get(String(authorId));

  if (!authorInfo && authorId > 0) {
    authorInfo = {
      ForeignId: authorId,
      Name: cached.author?.name || 'Unknown',
      Url: cached.author?.profileUrl || '',
      ImageUrl: '',
      Description: '',
      AverageRating: 0,
      RatingCount: 0,
      Works: [],
    };
    authorCache.set(String(authorId), authorInfo);
  }

  const book = {
    Asin: "",
    AverageRating: parseFloat(cached.avgRating) || 0,
    Contributors: [{ForeignId: authorId, Role: "Author"}],
    Description: cached.description?.html || '',
    EditionInformation: '',
    ForeignId: parseInt(cached.bookId),
    Format: "",
    ImageUrl: cached.imageUrl || '',
    IsEbook: true,
    Isbn13: null,
    Language: "eng",
    NumPages: cached.numPages || null,
    Publisher: "",
    RatingCount: cached.ratingsCount || 0,
    ReleaseDate: null,
    Title: cached.bookTitleBare || cached.title || '',
    Url: `https://www.goodreads.com${cached.bookUrl || ''}`,
  };

  return {
    work: book,
    author: authorInfo ? [authorInfo] : [],
    cached: true,
  };
}

const app = express();
app.use(express.json({limit: '10mb'}));

// Log ALL incoming requests
app.use((req, res, next) => {
  console.log(`REQ ${req.method} ${req.headers.host}${req.url}`);
  next();
});

// Route based on Host header:
// - www.goodreads.com → proxy to real Goodreads (cache autocomplete)
// - api.bookinfo.club → bookinfo API (use cached data)

// Proxy all www.goodreads.com requests to real Goodreads
app.use((req, res, next) => {
  const host = req.headers.host || '';
  if (host.includes('goodreads')) {
    const path = req.url || '/';
    return proxyToGoodreads(req, res, path);
  }
  next();
});

// === BookInfo API endpoints (api.bookinfo.club) ===

// GET /v1/author/:id - get author info
app.get('/v1/author/:id', async (req, res) => {
  const id = req.params.id;
  console.log(`GET /v1/author/${id}`);

  // Use cache only (scraping fails due to WAF)
  const cached = authorCache.get(String(id));
  if (cached) {
    res.status(200).json({...cached, Works: []});
  } else {
    // Build minimal author from any cached books by this author
    const authorBooks = [...bookCache.values()].filter(b => String(b.author?.id) === String(id));
    if (authorBooks.length > 0) {
      const a = authorBooks[0].author;
      const authorInfo = {
        ForeignId: a.id,
        Name: a.name,
        Url: a.profileUrl || '',
        ImageUrl: '',
        Description: '',
        AverageRating: 0,
        RatingCount: 0,
        Works: [],
      };
      authorCache.set(String(id), authorInfo);
      saveCache();
      res.status(200).json({...authorInfo, Works: []});
    } else {
      res.status(404).json({error: 'Author not found', id});
    }
  }
});

// GET /v1/work/:id - get work info
app.get('/v1/work/:id', async (req, res) => {
  const id = req.params.id;
  console.log(`GET /v1/work/${id}`);

  const cached = buildWorkFromCache(id);
  if (cached) {
    const response = {
      ForeignId: cached.work.ForeignId,
      Title: cached.work.Title,
      Url: cached.work.Url,
      Genres: [],
      RelatedWorks: [],
      Books: [cached.work],
      Series: [],
      Authors: cached.author,
    };
    res.json(response);
    return;
  }

  res.status(404).json({error: 'Work not found (not in cache)', id});
});

// GET /v1/book/:id - redirect to work or author
app.get('/v1/book/:id', async (req, res) => {
  const id = req.params.id;
  console.log(`GET /v1/book/${id} (redirect)`);
  const cached = bookCache.get(String(id));
  if (cached && cached.author?.id) {
    res.redirect(302, `/v1/author/${cached.author.id}`);
  } else {
    res.redirect(302, `/v1/work/${id}`);
  }
});

// POST /v1/book/bulk - bulk book lookup (main search endpoint)
app.post('*', async (req, res) => {
  const ids = req.body;
  console.log(`POST bulk lookup: ${ids?.length} books`);

  if (!Array.isArray(ids)) {
    res.status(400).json({error: 'Expected array of IDs'});
    return;
  }

  const authors = {};
  const works = [];
  const failedIds = [];

  for (const id of ids) {
    let bookResult = null;

    // Cache only (scraping fails due to Goodreads WAF)
    const cached = buildWorkFromCache(id);
    if (cached) {
      bookResult = cached;
    } else {
      failedIds.push(id);
    }

    if (bookResult) {
      // Add author from cache if available
      if (bookResult.author && bookResult.author.length > 0) {
        const authorInfo = bookResult.author[0];
        if (authorInfo.ForeignId && !authors[authorInfo.ForeignId]) {
          authors[authorInfo.ForeignId] = authorInfo;
        }
      }

      works.push({
        ForeignId: bookResult.work.ForeignId,
        Title: bookResult.work.Title,
        Url: bookResult.work.Url,
        Genres: [],
        RelatedWorks: [],
        Books: [bookResult.work],
        Series: [],
      });
    }
  }

  const response = {
    Works: works,
    Series: [],
    Authors: Object.values(authors),
  };

  console.log(`Responding with ${works.length} works, ${Object.keys(authors).length} authors`);
  if (failedIds.length > 0) {
    console.log(`Failed IDs: ${failedIds.join(', ')}`);
  }

  res.json(response);
});

const httpServer = http.createServer(app);

import tls from "tls";

// HTTPS server with both certs (using SNI)
const httpsOptions = {
  SNICallback: (servername, cb) => {
    let keyPath, certPath;
    if (servername.includes('goodreads')) {
      keyPath = './certs/goodreads.key';
      certPath = './certs/goodreads.crt';
    } else {
      keyPath = './certs/bookinfo-club.key';
      certPath = './certs/bookinfo-club.crt';
    }
    try {
      const ctx = tls.createSecureContext({
        key: fs.readFileSync(keyPath, 'utf8'),
        cert: fs.readFileSync(certPath, 'utf8'),
      });
      cb(null, ctx);
    } catch (e) {
      cb(e, null);
    }
  },
  key: fs.readFileSync('./certs/bookinfo-club.key', 'utf8'),
  cert: fs.readFileSync('./certs/bookinfo-club.crt', 'utf8'),
};

httpServer.listen(80, () => {
  console.log('HTTP listening on :80');
});

https.createServer(httpsOptions, app).listen(443, () => {
  console.log('HTTPS listening on :443');
});
