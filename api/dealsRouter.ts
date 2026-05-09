import { z } from "zod";
import { createRouter, publicQuery } from "./middleware";
import {
  findAllDeals,
  findDealById,
  incrementClicks,
  getStats,
} from "./queries/deals";

export const dealsRouter = createRouter({
  list: publicQuery
    .input(
      z
        .object({
          platformId: z.number().optional(),
          categoryId: z.number().optional(),
          minDiscount: z.number().min(0).max(100).optional(),
          search: z.string().optional(),
          featured: z.boolean().optional(),
          sortBy: z.enum(["discount", "price", "newest"]).optional(),
        })
        .optional()
    )
    .query(({ input }) => {
      return findAllDeals(input ?? {});
    }),

  byId: publicQuery
    .input(z.object({ id: z.number() }))
    .query(({ input }) => {
      return findDealById(input.id);
    }),

  click: publicQuery
    .input(z.object({ id: z.number() }))
    .mutation(({ input }) => {
      return incrementClicks(input.id);
    }),

  stats: publicQuery.query(() => {
    return getStats();
  }),
});
