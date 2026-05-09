import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, TrendingDown } from "lucide-react";
import { trpc } from "@/providers/trpc";

type DealCardProps = {
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
    isFeatured: boolean;
    platformName: string;
    platformCode: string;
    platformColor: string | null;
    categoryName: string;
    categorySlug: string;
  };
};

export default function DealCard({ deal }: DealCardProps) {
  const clickMutation = trpc.deals.click.useMutation();

  const handleClick = () => {
    clickMutation.mutate({ id: deal.id });
    window.open(deal.productUrl, "_blank", "noopener,noreferrer");
  };

  const savings = (
    parseFloat(deal.originalPrice) - parseFloat(deal.salePrice)
  ).toFixed(0);

  const getPlatformBg = (code: string) => {
    switch (code) {
      case "amazon-eg":
        return "bg-[#FF9900]/10 text-[#FF9900] border-[#FF9900]/20";
      case "noon-eg":
        return "bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950/30 dark:text-yellow-400";
      case "jumia-eg":
        return "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/30 dark:text-orange-400";
      default:
        return "bg-gray-100 text-gray-700";
    }
  };

  return (
    <Card className="group overflow-hidden border-0 shadow-sm hover:shadow-lg transition-all duration-300 bg-white dark:bg-gray-900">
      {/* Image Container */}
      <div className="relative aspect-square overflow-hidden bg-gray-100 dark:bg-gray-800">
        {deal.imageUrl ? (
          <img
            src={deal.imageUrl}
            alt={deal.title}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-gray-400">
            <TrendingDown className="h-12 w-12" />
          </div>
        )}

        {/* Discount Badge */}
        <div className="absolute top-3 left-3">
          <Badge
            className="bg-red-600 hover:bg-red-700 text-white font-bold text-sm px-2.5 py-1"
          >
            -{deal.discountPercent}%
          </Badge>
        </div>

        {/* Featured Badge */}
        {deal.isFeatured && (
          <div className="absolute top-3 right-3">
            <Badge
              variant="secondary"
              className="bg-amber-400 hover:bg-amber-500 text-amber-900 font-semibold text-xs"
            >
              FEATURED
            </Badge>
          </div>
        )}

        {/* Platform Badge */}
        <div className="absolute bottom-3 left-3">
          <Badge
            variant="outline"
            className={`${getPlatformBg(deal.platformCode)} text-xs font-semibold`}
          >
            {deal.platformName}
          </Badge>
        </div>
      </div>

      {/* Content */}
      <CardContent className="p-4">
        {/* Category */}
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1.5">
          {deal.categoryName}
        </p>

        {/* Title */}
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 line-clamp-2 mb-2 leading-snug min-h-[2.5rem]">
          {deal.title}
        </h3>

        {/* Description */}
        {deal.description && (
          <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 mb-3">
            {deal.description}
          </p>
        )}

        {/* Price Row */}
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
            {deal.salePrice} <span className="text-sm">{deal.currency}</span>
          </span>
        </div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm text-gray-400 line-through">
            {deal.originalPrice} {deal.currency}
          </span>
          <span className="text-xs font-medium text-green-600 dark:text-green-400">
            Save {savings} {deal.currency}
          </span>
        </div>

        {/* CTA Button */}
        <Button
          onClick={handleClick}
          className="w-full bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700 text-white font-semibold"
          size="sm"
        >
          <ExternalLink className="h-4 w-4 mr-1.5" />
          View Deal
        </Button>
      </CardContent>
    </Card>
  );
}
