#!/usr/bin/env node

const pup = require('puppeteer-core');
const http = require('http');
const fs = require('fs');
const url = require('url');


function describe(jsHandle) {
  return jsHandle.executionContext().evaluate((obj) => {
    return obj;
    // serialize |obj| however you want
    return `OBJ: ${typeof obj}, ${obj}`;
  }, jsHandle);
}


function delay(t, value) {
  return new Promise(resolve => setTimeout(resolve, t || 0, value));
}


async function timeout(promise, t) {
  var ret = Promise.race([promise, delay(t || 1000, 'timeout')]);
  if (ret == 'timeout')
    throw new Error(ret);
  return ret;
}


const RED =   '\x1b[31m%s\x1b[0m';
const GREEN = '\x1b[32m%s\x1b[0m';
const YELLOW = '\x1b[33m%s\x1b[0m';

function indicator(success) {
  return success ? '🟢' : '🔴';
}


async function runTests(browser, base, url, needsTrigger) {
  console.log(YELLOW, `🔄 Tests at ${url}`);
  let page = await browser.newPage();
  page.on('console', async msg => {
    if (msg.type() == 'debug')
      return;
    var args = await Promise.all(msg.args().map(describe));
    console.log(msg.type() == 'error' ? RED : '%s',
                args.join(' '))
  });
  page.on('pageerror', e => console.log(e.toString()));

  await page.goto(base + url);
  await page.setViewport({width: 1080, height: 1024});

  var res = new Promise(async resolve => {
    var timeout = setTimeout(async () => {
      console.log('TIMEOUT WAITING FOR TESTS', url);
      await page.close();
      resolve(false);
    }, 10000);

    await page.exposeFunction('headlessRunnerDone', async (success) => {
      clearTimeout(timeout);
      // wait for all logs to resolve
      await new Promise(r => setTimeout(r, 10));
      await page.close();
      resolve(success);
    });

    await page.evaluate(() => {
      document.querySelector('#tinytest').addEventListener('tt-done', (e) => {
        console.log('Event:', e.type, 'Success:', e.detail.success);
        setTimeout(() => window.headlessRunnerDone(e.detail.success));
      });
    });

    if (needsTrigger) {
      await page.evaluate(() => {
        window.dispatchEvent(new CustomEvent('run-tests', {detail: {sync: true}}));
      });
    }
  });

  var success = await res;
  console.log(success ? GREEN : RED,
              `${indicator(success)} ${url} is done, success: ${success}`);
  return success;
}


function staticHandler(root) {
  return function (req, res) {
    var path = url.parse(req.url).pathname;
    if (path.endsWith('/')) {
      path += 'index.html';
    }
    fs.readFile(root + '/' + path.slice(1), (err, data) => {
      if (err) {
        res.writeHead(404, 'Not Found');
        res.write('Not Found');
        return res.end();
      }
      res.writeHead(200);
      res.write(data);
      return res.end();
    });
  }
}


(async () => {
  var path = process.env.CHROMIUM_BIN ||
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  let browser = await pup.launch({
    headless: true,
    executablePath: path,
  });

  var root = process.argv[2] || 'public';
  var server = await http.createServer(staticHandler(root)).listen(0);
  var base = 'http://localhost:' + server.address().port;

  var success = await runTests(browser, base, '/test/morph/', false) &&
      await runTests(browser, base, '/examples/', true);
  console.log(success ? GREEN : RED,
              `${indicator(success)} ALL TESTS DONE, SUCCESS: ${success}`);
  await browser.close();
  process.exit(success ? 0 : 1);
})();
