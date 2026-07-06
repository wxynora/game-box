import { fileURLToPath } from "node:url";
import fs from "node:fs";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const gameRoot = path.resolve(here, "../../..");
const candidateNodeModules = [
  process.env.SESE_BOARD_NODE_MODULES,
  path.resolve(here, "node_modules"),
  path.resolve(gameRoot, "node_modules"),
].filter(Boolean);
const nodeModules = candidateNodeModules.find((dir) =>
  fs.existsSync(path.join(dir, "react")) && fs.existsSync(path.join(dir, "react-dom"))
);
const alias = nodeModules
  ? {
      react: path.join(nodeModules, "react"),
      "react-dom": path.join(nodeModules, "react-dom"),
      "react-dom/client": path.join(nodeModules, "react-dom/client.js"),
      "react/jsx-runtime": path.join(nodeModules, "react/jsx-runtime.js"),
    }
  : {};
const fsAllow = nodeModules ? [gameRoot, nodeModules] : [gameRoot];

export default {
  root: here,
  resolve: {
    alias,
  },
  server: {
    host: "127.0.0.1",
    port: 5176,
    strictPort: false,
    fs: {
      allow: fsAllow,
    },
  },
};
