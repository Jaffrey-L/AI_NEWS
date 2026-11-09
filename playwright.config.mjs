export default {
  testDir: "./tests",
  timeout: 30000,
  use: {
    baseURL: process.env.SITE_URL || "http://127.0.0.1:8000",
    viewport: { width: 1440, height: 950 }
  }
};
