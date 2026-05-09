# Egypt Deals - Discount Aggregator App

A full-stack web application that aggregates the best deals and discounts (40%+) from **Amazon Egypt**, **Noon Egypt**, and **Jumia Egypt**.

## Features

- **Deals Dashboard**: Browse deals with filters by platform, category, discount percentage, and search
- **Featured Deals**: Highlighted deals section on homepage
- **Admin Panel**: Add, edit, and delete deals (admin only)
- **Authentication**: OAuth 2.0 login with role-based access
- **Responsive Design**: Works on mobile, tablet, and desktop

## Tech Stack

- **Frontend**: React 19 + TypeScript + Tailwind CSS + shadcn/ui
- **Backend**: Hono + tRPC 11 + Drizzle ORM + MySQL
- **Auth**: OAuth 2.0 with JWT sessions

## Project Structure

```
├── src/                  # Frontend
│   ├── pages/            # Route pages (Home, Admin, Login)
│   ├── components/       # UI components
│   ├── hooks/            # Custom hooks (useAuth)
│   └── providers/        # tRPC provider
├── api/                  # Backend
│   ├── dealsRouter.ts    # Deals API endpoints
│   ├── platformsRouter.ts
│   ├── categoriesRouter.ts
│   ├── adminRouter.ts    # Admin-only endpoints
│   └── queries/          # Database query functions
├── db/
│   ├── schema.ts         # Database tables
│   └── seed.ts           # Seed data (50+ real deals)
└── contracts/            # Shared types/constants
```

## Database Schema

- **users** - Authenticated users with roles
- **platforms** - Amazon Egypt, Noon Egypt, Jumia Egypt
- **categories** - Electronics, Fashion, Home & Kitchen, Beauty, etc.
- **deals** - Product deals with pricing, discounts, URLs

## API Endpoints (tRPC)

### Public
- `deals.list` - List deals with filters
- `deals.byId` - Get single deal
- `deals.click` - Track click-through
- `deals.stats` - Get aggregate statistics
- `platforms.list` - List all platforms
- `categories.list` / `categories.top` - List categories

### Admin Only
- `admin.deals` - List all deals for management
- `admin.dealCreate` - Create new deal
- `admin.dealUpdate` - Update existing deal
- `admin.dealDelete` - Delete deal

## Deployment

### Railway.app (Recommended - Free Tier Available)

1. Push code to GitHub
2. Connect Railway to your GitHub repo
3. Add MySQL database (or connect external)
4. Set environment variables
5. Deploy

### Render.com

1. Push code to GitHub
2. Create new Web Service
3. Set build command: `npm run build`
4. Set start command: `npm start`
5. Add environment variables
6. Deploy

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | MySQL connection string |
| `APP_ID` | Application ID |
| `APP_SECRET` | Application secret |
| `VITE_APP_ID` | Frontend app ID |
| `VITE_KIMI_AUTH_URL` | OAuth provider URL |
| `KIMI_AUTH_URL` | Backend auth URL |
| `KIMI_OPEN_URL` | Open platform URL |
| `OWNER_UNION_ID` | Owner union ID |

## Development

```bash
# Install dependencies
npm install

# Push database schema
npm run db:push

# Seed database with deals
npx tsx db/seed.ts

# Start dev server
npm run dev
```

## Adding Real Scraping Later

The app includes an admin panel for manual deal curation. To add automated scraping:

1. Get affiliate API access from Amazon Associates, Noon Partners, Jumia Affiliates
2. Create a scraper service in `api/scraper/`
3. Schedule it with a cron job or background worker
4. Insert scraped deals using the existing `createDeal` function

## License

MIT
