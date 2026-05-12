import Database from "better-sqlite3";
import crypto from "crypto";
import path from "path";

const DB_PATH = process.env.USER_DB_PATH || path.join(import.meta.dirname, "..", "h5-chat", "bridge", "users.db");

let db: Database.Database;

function getDb(): Database.Database {
  if (db) return db;
  db = new Database(DB_PATH, { readonly: false });
  db.pragma("journal_mode = WAL");
  return db;
}

export interface User {
  id: number;
  username: string;
  password_hash: string;
  role: string;
  display_name: string;
  enabled: number;
}

function hashPassword(password: string): string {
  return crypto.createHash("sha256").update(password).digest("hex");
}

export function login(
  username: string,
  password: string
): { token: string; username: string; role: string; display_name: string } | null {
  const d = getDb();
  const user = d
    .prepare("SELECT * FROM users WHERE username = ? AND enabled = 1")
    .get(username) as User | undefined;
  if (!user) return null;

  if (user.password_hash !== hashPassword(password)) return null;

  const token = crypto.randomBytes(32).toString("base64url");
  const now = Date.now() / 1000;
  d.prepare("INSERT INTO tokens (user_id, token, created_at, expires_at) VALUES (?, ?, ?, 0)")
    .run(user.id, token, now);
  d.prepare("UPDATE users SET last_login = ? WHERE id = ?").run(now, user.id);

  return {
    token,
    username: user.username,
    role: user.role,
    display_name: user.display_name,
  };
}

export interface TokenUser {
  userId: number;
  username: string;
  role: string;
  displayName: string;
}

export function validateToken(token: string): TokenUser | null {
  const d = getDb();
  const row = d
    .prepare(
      `SELECT t.user_id, u.username, u.role, u.display_name, u.enabled
       FROM tokens t JOIN users u ON t.user_id = u.id
       WHERE t.token = ? AND u.enabled = 1`
    )
    .get(token) as any | undefined;
  if (!row) return null;
  return {
    userId: row.user_id,
    username: row.username,
    role: row.role,
    displayName: row.display_name,
  };
}

export function logout(token: string): void {
  getDb().prepare("DELETE FROM tokens WHERE token = ?").run(token);
}

export function changePassword(
  userId: number,
  oldPassword: string,
  newPassword: string
): { ok: boolean; message?: string } {
  const d = getDb();
  const user = d.prepare("SELECT password_hash FROM users WHERE id = ?").get(userId) as User | undefined;
  if (!user) return { ok: false, message: "User not found" };
  if (user.password_hash !== hashPassword(oldPassword))
    return { ok: false, message: "Old password incorrect" };
  d.prepare("UPDATE users SET password_hash = ? WHERE id = ?")
    .run(hashPassword(newPassword), userId);
  // Revoke all tokens for this user
  d.prepare("DELETE FROM tokens WHERE user_id = ?").run(userId);
  return { ok: true };
}
