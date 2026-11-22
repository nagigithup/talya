/* Test dependencies stay outside application assets and production settings. */
const path = require('node:path');
const app = path.resolve(__dirname, '../..');
const bench = path.resolve(app, '../..');
const base = process.env.TALYA_BASE_URL || 'http://talya.localhost:8000';
if (new URL(base).origin !== 'http://talya.localhost:8000') {
  throw new Error('Talya browser tests are restricted to local talya.localhost:8000');
}
let playwright;
if (process.env.TALYA_PLAYWRIGHT_PATH) {
  playwright = require(process.env.TALYA_PLAYWRIGHT_PATH);
} else {
  try { playwright = require('playwright'); }
  catch (error) {
    throw new Error('Install Playwright or set TALYA_PLAYWRIGHT_PATH to its module directory.', { cause: error });
  }
}
module.exports = { app, bench, base, playwright };
