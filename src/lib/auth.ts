"use server";

import { db } from "~/db";
import { users, sessions } from "~/db/schema";
import { eq, and, gt } from "drizzle-orm";
import { useSession } from "vinxi/http";
import { redirect } from "@solidjs/router";

function generateId() {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let id = "";
  for (let i = 0; i < 40; i++) id += chars[Math.floor(Math.random() * chars.length)];
  return id;
}

function sessionPassword() {
  const secret = process.env.API_SECRET || process.env.SESSION_SECRET;
  if (!secret || secret.length < 32) {
    throw new Error(
      "API_SECRET must be set and at least 32 characters. Configure it in Vercel Environment Variables."
    );
  }
  return secret;
}

async function getSessionManager() {
  return useSession<{ sessionId?: string }>({
    password: sessionPassword(),
  });
}

export async function login(username: string, password: string): Promise<{ ok: boolean; error?: string }> {
  try {
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
    const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);

    await db.insert(sessions).values({ id: sessionId, userId: user.id, expiresAt });

    const session = await getSessionManager();
    await session.update({ sessionId });

    return { ok: true };
  } catch (e) {
    console.error("[login]", e);
    return { ok: false, error: e instanceof Error ? e.message : "登录失败，请检查服务端配置" };
  }
}

export async function logout() {
  try {
    const session = await getSessionManager();
    const data = await session.data;
    if (data.sessionId) {
      await db.delete(sessions).where(eq(sessions.id, data.sessionId));
    }
    await session.update({ sessionId: undefined });
  } catch (e) {
    console.error("[logout]", e);
  }
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
  } catch (e) {
    console.error("[getAuthUser]", e);
    return null;
  }
}

/** Server-side guard: redirect to login if not authenticated. */
export async function requireAuth() {
  const user = await getAuthUser();
  if (!user) throw redirect("/login");
  return user;
}
