import { createRouter, publicQuery } from "./middleware";
import { findAllCategories, findTopCategories } from "./queries/categories";

export const categoriesRouter = createRouter({
  list: publicQuery.query(() => {
    return findAllCategories();
  }),

  top: publicQuery.query(() => {
    return findTopCategories();
  }),
});
