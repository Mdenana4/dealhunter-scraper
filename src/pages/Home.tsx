import { useState } from "react";
import { trpc } from "@/providers/trpc";
import Layout from "@/components/Layout";
import DealCard from "@/components/DealCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Search,
  SlidersHorizontal,
  Percent,
  Store,
  Grid3X3,
  LayoutList,
  TrendingDown,
  Flame,
  ArrowUpDown,
} from "lucide-react";

const DISCOUNT_TIERS = [
  { label: "All", value: 0 },
  { label: "40%+", value: 40 },
  { label: "50%+", value: 50 },
  { label: "60%+", value: 60 },
  { label: "70%+", value: 70 },
];

const SORT_OPTIONS = [
  { label: "Newest", value: "newest" },
  { label: "Biggest Discount", value: "discount" },
  { label: "Lowest Price", value: "price" },
] as const;

export default function Home() {
  const [search, setSearch] = useState("");
  const [selectedPlatform, setSelectedPlatform] = useState<number | undefined>();
  const [selectedCategory, setSelectedCategory] = useState<number | undefined>();
  const [minDiscount, setMinDiscount] = useState<number>(0);
  const [sortBy, setSortBy] = useState<"discount" | "price" | "newest">("newest");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [showFilters, setShowFilters] = useState(false);

  const { data: deals, isLoading } = trpc.deals.list.useQuery({
    platformId: selectedPlatform,
    categoryId: selectedCategory,
    minDiscount: minDiscount > 0 ? minDiscount : undefined,
    search: search || undefined,
    sortBy,
  });

  const { data: platforms } = trpc.platforms.list.useQuery();
  const { data: categories } = trpc.categories.list.useQuery();
  const { data: stats } = trpc.deals.stats.useQuery();

  const featuredDeals = trpc.deals.list.useQuery({ featured: true });

  const filteredDeals = deals?.filter((d) => {
    if (minDiscount > 0 && d.discountPercent < minDiscount) return false;
    if (search && !d.title.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }) ?? [];

  return (
    <Layout>
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-orange-600 via-red-600 to-pink-600 text-white">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wOCI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />
        <div className="relative mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/20 backdrop-blur text-sm font-medium mb-4">
              <Flame className="h-4 w-4" />
              Live Deals Updated Daily
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-3">
              Best Deals in Egypt
            </h1>
            <p className="text-lg text-white/90 mb-6">
              Hand-picked discounts 40%+ from Amazon, Noon & Jumia Egypt
            </p>

            {/* Stats */}
            {stats && (
              <div className="flex items-center justify-center gap-6 sm:gap-10 text-sm">
                <div className="text-center">
                  <p className="text-2xl font-bold">{stats.total || 0}</p>
                  <p className="text-white/70">Active Deals</p>
                </div>
                <div className="w-px h-10 bg-white/20" />
                <div className="text-center">
                  <p className="text-2xl font-bold">{Math.round(stats.avgDiscount || 0)}%</p>
                  <p className="text-white/70">Avg Discount</p>
                </div>
                <div className="w-px h-10 bg-white/20" />
                <div className="text-center">
                  <p className="text-2xl font-bold">{stats.maxDiscount || 0}%</p>
                  <p className="text-white/70">Best Deal</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Featured Deals */}
      {featuredDeals.data && featuredDeals.data.length > 0 && (
        <section className="bg-white dark:bg-gray-950 border-b dark:border-gray-800">
          <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
            <div className="flex items-center gap-2 mb-4">
              <Flame className="h-5 w-5 text-orange-500" />
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Featured Deals</h2>
            </div>
            <div className="flex gap-4 overflow-x-auto pb-2 snap-x snap-mandatory scrollbar-hide">
              {featuredDeals.data.slice(0, 6).map((deal) => (
                <div key={deal.id} className="snap-start shrink-0 w-[280px] sm:w-[320px]">
                  <DealCard deal={deal} />
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Filters & Search */}
      <section className="bg-white dark:bg-gray-950 sticky top-16 z-40 border-b dark:border-gray-800 shadow-sm">
        <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8">
          {/* Search Bar */}
          <div className="flex gap-2 mb-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search deals..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 h-10"
              />
            </div>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setShowFilters(!showFilters)}
              className={showFilters ? "border-orange-500 text-orange-600" : ""}
            >
              <SlidersHorizontal className="h-4 w-4" />
            </Button>
            <div className="hidden sm:flex border rounded-md overflow-hidden">
              <Button
                variant={viewMode === "grid" ? "default" : "ghost"}
                size="icon"
                className="rounded-none h-10 w-10"
                onClick={() => setViewMode("grid")}
              >
                <Grid3X3 className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === "list" ? "default" : "ghost"}
                size="icon"
                className="rounded-none h-10 w-10"
                onClick={() => setViewMode("list")}
              >
                <LayoutList className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Expandable Filters */}
          {showFilters && (
            <div className="space-y-3 pb-3 border-t pt-3 dark:border-gray-800">
              {/* Platforms */}
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 flex items-center gap-1">
                  <Store className="h-3 w-3" /> Platform
                </p>
                <div className="flex flex-wrap gap-1.5">
                  <Badge
                    variant={selectedPlatform === undefined ? "default" : "outline"}
                    className="cursor-pointer"
                    onClick={() => setSelectedPlatform(undefined)}
                  >
                    All
                  </Badge>
                  {platforms?.map((p) => (
                    <Badge
                      key={p.id}
                      variant={selectedPlatform === p.id ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => setSelectedPlatform(p.id)}
                    >
                      {p.name}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Categories */}
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 flex items-center gap-1">
                  <TrendingDown className="h-3 w-3" /> Category
                </p>
                <div className="flex flex-wrap gap-1.5">
                  <Badge
                    variant={selectedCategory === undefined ? "default" : "outline"}
                    className="cursor-pointer"
                    onClick={() => setSelectedCategory(undefined)}
                  >
                    All
                  </Badge>
                  {categories?.map((c) => (
                    <Badge
                      key={c.id}
                      variant={selectedCategory === c.id ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => setSelectedCategory(c.id)}
                    >
                      {c.name}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Discount Tiers */}
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 flex items-center gap-1">
                  <Percent className="h-3 w-3" /> Min Discount
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {DISCOUNT_TIERS.map((tier) => (
                    <Badge
                      key={tier.value}
                      variant={minDiscount === tier.value ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => setMinDiscount(tier.value)}
                    >
                      {tier.label}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Sort */}
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 flex items-center gap-1">
                  <ArrowUpDown className="h-3 w-3" /> Sort By
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {SORT_OPTIONS.map((opt) => (
                    <Badge
                      key={opt.value}
                      variant={sortBy === opt.value ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => setSortBy(opt.value)}
                    >
                      {opt.label}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Deals Grid */}
      <section className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="space-y-3">
                <Skeleton className="aspect-square rounded-lg" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-8 w-full" />
              </div>
            ))}
          </div>
        ) : filteredDeals.length === 0 ? (
          <div className="text-center py-16">
            <Search className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
              No deals found
            </h3>
            <p className="text-gray-500 dark:text-gray-400">
              Try adjusting your filters or search query
            </p>
          </div>
        ) : (
          <>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              {filteredDeals.length} deal{filteredDeals.length !== 1 ? "s" : ""} found
              {minDiscount > 0 && ` with ${minDiscount}%+ discount`}
            </p>
            <div
              className={
                viewMode === "grid"
                  ? "grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4"
                  : "space-y-3"
              }
            >
              {filteredDeals.map((deal) =>
                viewMode === "grid" ? (
                  <DealCard key={deal.id} deal={deal} />
                ) : (
                  <DealListRow key={deal.id} deal={deal} />
                )
              )}
            </div>
          </>
        )}
      </section>
    </Layout>
  );
}

function DealListRow({
  deal,
}: {
  deal: {
    id: number;
    title: string;
    description: string | null;
    productUrl: string;
    imageUrl: string | null;
    originalPrice: string;
    salePrice: string;
    discountPercent: number;
    currency: string;
    platformName: string;
    platformCode: string;
    platformColor: string | null;
    categoryName: string;
  };
}) {
  const clickMutation = trpc.deals.click.useMutation();

  const handleClick = () => {
    clickMutation.mutate({ id: deal.id });
    window.open(deal.productUrl, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="flex gap-4 p-3 rounded-lg border bg-white dark:bg-gray-900 dark:border-gray-800 hover:shadow-md transition-shadow">
      <div className="w-24 h-24 shrink-0 rounded-md overflow-hidden bg-gray-100 dark:bg-gray-800">
        {deal.imageUrl ? (
          <img src={deal.imageUrl} alt={deal.title} className="w-full h-full object-cover" loading="lazy" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-gray-400">
            <TrendingDown className="h-8 w-8" />
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">{deal.categoryName}</p>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
              {deal.title}
            </h3>
            {deal.description && (
              <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-1">{deal.description}</p>
            )}
          </div>
          <Badge className="bg-red-600 text-white shrink-0">-{deal.discountPercent}%</Badge>
        </div>
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold">{deal.salePrice} {deal.currency}</span>
            <span className="text-sm text-gray-400 line-through">{deal.originalPrice} {deal.currency}</span>
          </div>
          <Button
            size="sm"
            onClick={handleClick}
            className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700 text-white"
          >
            View Deal
          </Button>
        </div>
      </div>
    </div>
  );
}
