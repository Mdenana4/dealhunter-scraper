import { getDb } from "./connection";
import { categories } from "@db/schema";
import { eq, isNull, and, asc } from "drizzle-orm";

export async function findAllCategories() {
  return getDb()
    .select()
    .from(categories)
    .where(eq(categories.isActive, true))
    .orderBy(asc(categories.displayOrder), categories.name);
}

export async function findTopCategories() {
  return getDb()
    .select()
    .from(categories)
    .where(
      and(eq(categories.isActive, true), isNull(categories.parentId))
    )
    .orderBy(asc(categories.displayOrder), categories.name);
}

export async function findCategoryById(id: number) {
  const result = await getDb()
    .select()
    .from(categories)
    .where(eq(categories.id, id))
    .limit(1);
  return result[0] ?? null;
}
