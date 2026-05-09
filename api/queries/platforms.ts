import { getDb } from "./connection";
import { platforms } from "@db/schema";
import { eq } from "drizzle-orm";

export async function findAllPlatforms() {
  return getDb()
    .select()
    .from(platforms)
    .where(eq(platforms.isActive, true))
    .orderBy(platforms.name);
}

export async function findPlatformById(id: number) {
  const result = await getDb()
    .select()
    .from(platforms)
    .where(eq(platforms.id, id))
    .limit(1);
  return result[0] ?? null;
}
