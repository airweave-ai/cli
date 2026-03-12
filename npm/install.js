const { execSync } = require("child_process");
const { version } = require("./package.json");

const pip = process.platform === "win32" ? "pip" : "pip3";
const pkg = `airweave-cli==${version}`;

try {
  execSync(`${pip} install ${pkg}`, { stdio: "inherit" });
} catch {
  console.error(
    `\nFailed to install ${pkg}.\n` +
      "Make sure Python 3.9+ and pip are installed, then run:\n" +
      `  ${pip} install ${pkg}\n`
  );
  // Don't fail the npm install — the user can install the Python package manually
}
