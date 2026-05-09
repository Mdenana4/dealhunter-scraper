import { authRouter } from "./auth-router";
import { dealsRouter } from "./dealsRouter";
import { platformsRouter } from "./platformsRouter";
import { categoriesRouter } from "./categoriesRouter";
import { adminRouter } from "./adminRouter";
import { createRouter, publicQuery } from "./middleware";

export const appRouter = createRouter({
  ping: publicQuery.query(() => ({ ok: true, ts: Date.now() })),
  auth: authRouter,
  deals: dealsRouter,
  platforms: platformsRouter,
  categories: categoriesRouter,
  admin: adminRouter,
});

export type AppRouter = typeof appRouter;
