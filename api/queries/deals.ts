import { getDb } from "./connection";
import { deals, platforms, categories } from "@db/schema";
import { eq, and, gte, desc, asc, like, sql } from "drizzle-orm";

export async function findAllDeals(filters?: {
  platformId?: number;
  categoryId?: number;
  minDiscount?: number;
  search?: string;
  featured?: boolean;
  sortBy?: "discount" | "price" | "newest";
}) {
  const db = getDb();
  const conditions = [eq(deals.isActive, true)];

  if (filters?.platformId) {
    conditions.push(eq(deals.platformId, filters.platformId));
  }
  if (filters?.categoryId) {
    conditions.push(eq(deals.categoryId, filters.categoryId));
  }
  if (filters?.minDiscount) {
    conditions.push(gte(deals.discountPercent, filters.minDiscount));
  }
  if (filters?.featured) {
    conditions.push(eq(deals.isFeatured, true));
  }
  if (filters?.search) {
    conditions.push(like(deals.title, `%${filters.search}%`));
  }

  let orderBy;
  switch (filters?.sortBy) {
    case "discount":
      orderBy = [desc(deals.discountPercent), desc(deals.createdAt)];
      break;
    case "price":
      orderBy = [asc(deals.salePrice)];
      break;
    case "newest":
    default:
      orderBy = [desc(deals.createdAt)];
  }

  const result = await db
    .select({
      id: deals.id,
      title: deals.title,
      description: deals.description,
      productUrl: deals.productUrl,
      imageUrl: deals.imageUrl,
      originalPrice: deals.originalPrice,
      salePrice: deals.salePrice,
      discountPercent: deals.discountPercent,
      currency: deals.currency,
      isFeatured: deals.isFeatured,
      isActive: deals.isActive,
      startDate: deals.startDate,
      endDate: deals.endDate,
      clicks: deals.clicks,
      createdAt: deals.createdAt,
      platformId: deals.platformId,
      categoryId: deals.categoryId,
      platformName: platforms.name,
      platformCode: platforms.code,
      platformColor: platforms.color,
      categoryName: categories.name,
      categorySlug: categories.slug,
    })
    .from(deals)
    .innerJoin(platforms, eq(deals.platformId, platforms.id))
    .innerJoin(categories, eq(deals.categoryId, categories.id))
    .where(and(...conditions))
    .orderBy(...orderBy);

  return result;
}

export async function findDealById(id: number) {
  const db = getDb();
  const result = await db
    .select({
      id: deals.id,
      title: deals.title,
      description: deals.description,
      productUrl: deals.productUrl,
      imageUrl: deals.imageUrl,
      originalPrice: deals.originalPrice,
      salePrice: deals.salePrice,
      discountPercent: deals.discountPercent,
      currency: deals.currency,
      isFeatured: deals.isFeatured,
      isActive: deals.isActive,
      startDate: deals.startDate,
      endDate: deals.endDate,
      clicks: deals.clicks,
      createdAt: deals.createdAt,
      updatedAt: deals.updatedAt,
      platformId: deals.platformId,
      categoryId: deals.categoryId,
      platformName: platforms.name,
      platformCode: platforms.code,
      platformColor: platforms.color,
      categoryName: categories.name,
      categorySlug: categories.slug,
    })
    .from(deals)
    .innerJoin(platforms, eq(deals.platformId, platforms.id))
    .innerJoin(categories, eq(deals.categoryId, categories.id))
    .where(eq(deals.id, id))
    .limit(1);

  return result[0] ?? null;
}

export async function incrementClicks(id: number) {
  const db = getDb();
  await db
    .update(deals)
    .set({ clicks: sql`${deals.clicks} + 1` })
    .where(eq(deals.id, id));
}

export async function createDeal(data: {
  platformId: number;
  categoryId: number;
  title: string;
  description?: string;
  productUrl: string;
  imageUrl?: string;
  originalPrice: string;
  salePrice: string;
  discountPercent: number;
  currency?: string;
  isFeatured?: boolean;
  endDate?: Date;
}) {
  const db = getDb();
  const [{ id }] = await db
    .insert(deals)
    .values({
      ...data,
      currency: data.currency ?? "EGP",
      isFeatured: data.isFeatured ?? false,
    })
    .$returningId();
  return findDealById(id);
}

export async function updateDeal(
  id: number,
  data: Partial<{
    platformId: number;
    categoryId: number;
    title: string;
    description: string;
    productUrl: string;
    imageUrl: string;
    originalPrice: string;
    salePrice: string;
    discountPercent: number;
    currency: string;
    isFeatured: boolean;
    isActive: boolean;
    endDate: Date | null;
  }>
) {
  const db = getDb();
  await db.update(deals).set(data).where(eq(deals.id, id));
  return findDealById(id);
}

export async function deleteDeal(id: number) {
  const db = getDb();
  await db.delete(deals).where(eq(deals.id, id));
  return { success: true };
}

export async function getStats() {
  const db = getDb();
  const allDeals = await db
    .select({
      total: sql<number>`count(*)`,
      avgDiscount: sql<number>`avg(${deals.discountPercent})`,
      maxDiscount: sql<number>`max(${deals.discountPercent})`,
      totalClicks: sql<number>`sum(${deals.clicks})`,
    })
    .from(deals)
    .where(eq(deals.isActive, true));

  return allDeals[0];
}
