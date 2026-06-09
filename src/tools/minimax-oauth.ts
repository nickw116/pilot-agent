#!/usr/bin/env npx tsx
/**
 * MiniMax OAuth 设备授权流程工具
 *
 * 用法：npx tsx src/tools/minimax-oauth.ts
 */

import { randomBytes, createHash } from "crypto";
import { readFileSync, writeFileSync } from "fs";
import { resolve } from "path";
import { exec } from "child_process";
import { platform } from "os";

const CLIENT_ID = "78257093-7e40-4613-99e0-527b14b39113";
const SCOPE = "group_id profile model.completion";
const CODE_URL = "https://api.minimaxi.com/oauth/code";
const TOKEN_URL = "https://api.minimaxi.com/oauth/token";
const ENV_PATH = resolve(import.meta.dirname, "../../.env");

function generateVerifier(): string {
  return randomBytes(32)
    .toString("base64url")
    .slice(0, 64);
}

function generateChallenge(verifier: string): string {
  return createHash("sha256").update(verifier).digest("base64url");
}


function openBrowser(url: string) {
  const os = platform();
  let cmd: string;
  if (os === "darwin") {
    cmd = `open "${url}"`;
  } else if (os === "win32") {
    cmd = `start "${url}"`;
  } else {
    cmd = `xdg-open "${url}"`;
  }
  exec(cmd, (err) => {
    if (err) {
      console.log("\n无法自动打开浏览器，请手动访问上面的链接。");
    } else {
      console.log("\n已在浏览器中打开授权页面...");
    }
  });
}

async function requestCode(verifier: string, challenge: string) {
  const res = await fetch(CODE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: CLIENT_ID,
      scope: SCOPE,
      grant_type: "urn:ietf:params:oauth:grant-type:user_code",
      code_challenge: challenge,
      code_challenge_method: "S256",
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to request code (${res.status}): ${text}`);
  }

  return res.json() as Promise<{
    user_code: string;
    verification_uri: string;
    verification_uri_complete?: string;
    device_code: string;
    expires_in: number;
    interval?: number;
  }>;
}

async function pollToken(deviceCode: string, verifier: string, intervalMs: number, expiresAt: number) {
  while (Date.now() < expiresAt) {
    await new Promise((r) => setTimeout(r, intervalMs));

    const res = await fetch(TOKEN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: CLIENT_ID,
        grant_type: "urn:ietf:params:oauth:grant-type:device_code",
        device_code: deviceCode,
        code_verifier: verifier,
      }),
    });

    const data = await res.json() as Record<string, string>;

    if (data.access_token) {
      return data;
    }

    if (data.error === "authorization_pending") {
      process.stdout.write(".");
      continue;
    }

    if (data.error === "slow_down") {
      intervalMs += 5000;
      continue;
    }

    if (data.error === "expired_token") {
      throw new Error("Device code expired. Please restart the flow.");
    }

    if (data.error === "access_denied") {
      throw new Error("Authorization was denied by the user.");
    }

    throw new Error(`Token error: ${data.error} — ${data.error_description}`);
  }

  throw new Error("Polling timed out. Device code expired.");
}

function saveToEnv(token: string) {
  let envContent: string;
  try {
    envContent = readFileSync(ENV_PATH, "utf-8");
  } catch {
    envContent = "";
  }

  const lines = envContent.split("\n").filter((l) => !l.startsWith("MINIMAX_API_KEY="));
  lines.push(`MINIMAX_API_KEY=${token}`);

  writeFileSync(ENV_PATH, lines.join("\n") + "\n");
  console.log(`\nSaved MINIMAX_API_KEY to ${ENV_PATH}`);
}

async function main() {
  const verifier = generateVerifier();
  const challenge = generateChallenge(verifier);

  console.log("Requesting device authorization...");
  const codeResp = await requestCode(verifier, challenge);

  console.log("\n========================================");
  console.log("MiniMax OAuth — Device Authorization");
  console.log("========================================");
  console.log(`\nUser Code: ${codeResp.user_code}`);
  console.log(`Visit:     ${codeResp.verification_uri}`);

  if (codeResp.verification_uri_complete) {
    console.log(`Direct:    ${codeResp.verification_uri_complete}`);
  }

  // 自动打开浏览器
  const authUrl = codeResp.verification_uri_complete || codeResp.verification_uri;
  openBrowser(authUrl);

  console.log("\nWaiting for authorization");

  const interval = (codeResp.interval ?? 5) * 1000;
  const expiresAt = Date.now() + (codeResp.expires_in ?? 900) * 1000;

  const tokenData = await pollToken(codeResp.device_code, verifier, interval, expiresAt);

  console.log(`\nAccess token received (expires in ${tokenData.expires_in ?? "N/A"}s)`);

  if (tokenData.group_id) {
    console.log(`Group ID: ${tokenData.group_id}`);
  }

  saveToEnv(tokenData.access_token);
  console.log("Done! MINIMAX_API_KEY is now available in .env");
}

main().catch((err) => {
  console.error("OAuth failed:", err.message);
  process.exit(1);
});
