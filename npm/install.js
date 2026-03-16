const { execSync } = require("child_process");
const { version } = require("./package.json");

const pip = process.platform === "win32" ? "pip" : "pip3";
const pkg = `airweave-cli==${version}`;

function tryExec(cmd) {
  try {
    execSync(cmd, { stdio: "inherit" });
    return true;
  } catch {
    return false;
  }
}

function hasBin(name) {
  try {
    execSync(`which ${name}`, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

const strategies = [];

if (hasBin("pipx")) strategies.push(`pipx install ${pkg}`);
if (hasBin("uv")) strategies.push(`uv tool install ${pkg}`);

strategies.push(
  `${pip} install --user ${pkg}`,
  `${pip} install --break-system-packages ${pkg}`,
  `${pip} install ${pkg}`
);

const installed = strategies.some((cmd) => {
  console.log(`airweave: trying ${cmd}`);
  return tryExec(cmd);
});

if (!installed) {
  console.error(
    `\n@airweave/cli: failed to install ${pkg}.\n` +
      "Install pipx (recommended) or uv first, then retry:\n" +
      "  brew install pipx && pipx ensurepath\n" +
      `  npm rebuild @airweave/cli\n` +
      "\nOr install manually:\n" +
      `  pipx install ${pkg}\n`
  );
}
