import { relations } from "drizzle-orm";
import { users, platforms, categories, deals } from "./schema";

export const usersRelations = relations(users, () => ({}));

export const platformsRelations = relations(platforms, ({ many }) => ({
  deals: many(deals),
}));

export const categoriesRelations = relations(categories, ({ many }) => ({
  deals: many(deals),
}));

export const dealsRelations = relations(deals, ({ one }) => ({
  platform: one(platforms, {
    fields: [deals.platformId],
    references: [platforms.id],
  }),
  category: one(categories, {
    fields: [deals.categoryId],
    references: [categories.id],
  }),
}));
