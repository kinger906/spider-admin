"use server";

import { db } from "~/db";
import { users, sessions } from "~/db/schema";
import { eq, and, gt } from "drizzle-orm";
import { useSession } from "vinxi/http";

function generateId() {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let id = "";
  for (let i = 0; i < 40; i++) id += chars[Math.floor(Math.random() * chars.length)];
  return id;
}

async function getSessionManager() {
  return useSession<{ sessionId?: string }>({
    password: process.env.API_SECRET || "spider-session-secret-key-min-32-chars!!",
  });
}

export async function login(username: string, password: string): Promise<{ ok: boolean; error?: string }> {
  const rows = await db
    .select()
    .from(users)
    .where(eq(users.username, username))
    .limit(1);

  const user = rows[0];
  if (!user || user.passwordHash !== password) {
    return { ok: false, error: "用户名或密码错误" };
  }

  const sessionId = generateId();
  const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000); // 7 days

  await db.insert(sessions).values({ id: sessionId, userId: user.id, expiresAt });

  const session = await getSessionManager();
  await session.update({ sessionId });

  return { ok: true };
}

export async function logout() {
  const session = await getSessionManager();
  const data = await session.data;
  if (data.sessionId) {
    await db.delete(sessions).where(eq(sessions.id, data.sessionId));
  }
  await session.update({ sessionId: undefined });
}

export async function getAuthUser() {
  try {
    const session = await getSessionManager();
    const data = await session.data;
    if (!data.sessionId) return null;

    const rows = await db
      .select({
        id: users.id,
        username: users.username,
        displayName: users.displayName,
        role: users.role,
      })
      .from(sessions)
      .innerJoin(users, eq(sessions.userId, users.id))
      .where(and(eq(sessions.id, data.sessionId), gt(sessions.expiresAt, new Date())))
      .limit(1);

    return rows[0] ?? null;
  } catch {
    return null;
  }
}
