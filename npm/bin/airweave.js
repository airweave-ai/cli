#!/usr/bin/env node

const { spawnSync } = require("child_process");

const result = spawnSync("airweave", process.argv.slice(2), {
  stdio: "inherit",
  shell: process.platform === "win32",
});

if (result.error) {
  if (result.error.code === "ENOENT") {
    console.error(
      "Error: 'airweave' command not found. Run: pip install airweave-cli"
    );
  } else {
    console.error("Error:", result.error.message);
  }
  process.exit(1);
}

process.exit(result.status ?? 1);
