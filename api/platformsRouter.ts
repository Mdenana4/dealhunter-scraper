import { createRouter, publicQuery } from "./middleware";
import { findAllPlatforms } from "./queries/platforms";

export const platformsRouter = createRouter({
  list: publicQuery.query(() => {
    return findAllPlatforms();
  }),
});
