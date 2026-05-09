import { z } from "zod";
import { createRouter, adminQuery } from "./middleware";
import {
  findAllDeals,
  createDeal,
  updateDeal,
  deleteDeal,
} from "./queries/deals";

export const adminRouter = createRouter({
  deals: adminQuery.query(() => {
    return findAllDeals({});
  }),

  dealCreate: adminQuery
    .input(
      z.object({
        platformId: z.number().min(1),
        categoryId: z.number().min(1),
        title: z.string().min(1).max(500),
        description: z.string().optional(),
        productUrl: z.string().url(),
        imageUrl: z.string().url().optional(),
        originalPrice: z.string().regex(/^\d+(\.\d{1,2})?$/),
        salePrice: z.string().regex(/^\d+(\.\d{1,2})?$/),
        discountPercent: z.number().min(1).max(99),
        currency: z.string().max(10).optional(),
        isFeatured: z.boolean().optional(),
        endDate: z.string().datetime().optional(),
      })
    )
    .mutation(({ input }) => {
      return createDeal({
        ...input,
        endDate: input.endDate ? new Date(input.endDate) : undefined,
      });
    }),

  dealUpdate: adminQuery
    .input(
      z.object({
        id: z.number().min(1),
        data: z.object({
          platformId: z.number().min(1).optional(),
          categoryId: z.number().min(1).optional(),
          title: z.string().min(1).max(500).optional(),
          description: z.string().optional(),
          productUrl: z.string().url().optional(),
          imageUrl: z.string().url().optional().or(z.literal("")),
          originalPrice: z.string().regex(/^\d+(\.\d{1,2})?$/).optional(),
          salePrice: z.string().regex(/^\d+(\.\d{1,2})?$/).optional(),
          discountPercent: z.number().min(1).max(99).optional(),
          currency: z.string().max(10).optional(),
          isFeatured: z.boolean().optional(),
          isActive: z.boolean().optional(),
          endDate: z.string().datetime().optional().or(z.literal(null)),
        }),
      })
    )
    .mutation(({ input }) => {
      const { id, data } = input;
      const updateData: any = { ...data };
      if (data.endDate === null) {
        updateData.endDate = null;
      } else if (data.endDate) {
        updateData.endDate = new Date(data.endDate);
      }
      if (data.imageUrl === "") {
        updateData.imageUrl = null;
      }
      return updateDeal(id, updateData);
    }),

  dealDelete: adminQuery
    .input(z.object({ id: z.number().min(1) }))
    .mutation(({ input }) => {
      return deleteDeal(input.id);
    }),
});
