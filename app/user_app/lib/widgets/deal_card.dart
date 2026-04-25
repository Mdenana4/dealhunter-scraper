import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../models/deal.dart';
import '../config/theme.dart';
import '../config/constants.dart';

class DealCard extends StatelessWidget {
  final Deal deal;
  final VoidCallback onTap;
  final VoidCallback onSaveToggle;
  final VoidCallback? onShare;

  const DealCard({
    super.key,
    required this.deal,
    required this.onTap,
    required this.onSaveToggle,
    this.onShare,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image + discount badge
            Stack(
              children: [
                ClipRRect(
                  borderRadius:
                      const BorderRadius.vertical(top: Radius.circular(16)),
                  child: AspectRatio(
                    aspectRatio: 16 / 9,
                    child: deal.imageUrl != null
                        ? CachedNetworkImage(
                            imageUrl: deal.imageUrl!,
                            fit: BoxFit.cover,
                            placeholder: (_, __) => Container(
                                color: Colors.grey.shade100,
                                child: const Icon(Icons.image_outlined,
                                    size: 48, color: Colors.grey)),
                            errorWidget: (_, __, ___) => Container(
                                color: Colors.grey.shade100,
                                child: const Icon(Icons.broken_image_outlined,
                                    size: 48, color: Colors.grey)),
                          )
                        : Container(
                            color: Colors.grey.shade100,
                            child: const Icon(Icons.shopping_bag_outlined,
                                size: 48, color: Colors.grey)),
                  ),
                ),

                // Discount badge
                Positioned(
                  top: 10,
                  left: 10,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: AppTheme.fake,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      deal.discountLabel,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        fontSize: 13,
                      ),
                    ),
                  ),
                ),

                // Verification badge (if verified)
                if (deal.verification != null)
                  Positioned(
                    top: 10,
                    right: 10,
                    child: _VerificationDot(deal.verification!),
                  ),

                // Save button
                Positioned(
                  bottom: 8,
                  right: 8,
                  child: GestureDetector(
                    onTap: onSaveToggle,
                    child: Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.9),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        deal.isSaved
                            ? Icons.bookmark_rounded
                            : Icons.bookmark_border_rounded,
                        color: deal.isSaved
                            ? AppTheme.primary
                            : Colors.grey.shade600,
                        size: 20,
                      ),
                    ),
                  ),
                ),
              ],
            ),

            // Content
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Store chip
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppTheme.primary.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          AppConstants.marketplaceNames[deal.marketplaceCountry]
                              ?? deal.storeName,
                          style: TextStyle(
                            fontSize: 11,
                            color: AppTheme.primary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      if (deal.category != null) ...[
                        const SizedBox(width: 6),
                        Flexible(
                          child: Text(
                            deal.category!,
                            style: TextStyle(
                                fontSize: 11, color: Colors.grey.shade500),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ],
                  ),

                  const SizedBox(height: 6),

                  // Product name
                  Text(
                    deal.name,
                    style: Theme.of(context).textTheme.titleMedium,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),

                  const SizedBox(height: 8),

                  // Prices row
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        deal.formattedPrice,
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              color: AppTheme.genuine,
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                      const SizedBox(width: 8),
                      if (deal.originalPrice != null)
                        Text(
                          deal.formattedOriginalPrice,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                decoration: TextDecoration.lineThrough,
                                color: Colors.grey,
                              ),
                        ),
                      const Spacer(),
                      if (deal.savingAmount.isNotEmpty)
                        Text(
                          'Save ${deal.savingAmount}',
                          style: TextStyle(
                            fontSize: 11,
                            color: AppTheme.genuine,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _VerificationDot extends StatelessWidget {
  final VerificationSummary v;
  const _VerificationDot(this.v);

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.verificationColor(v.verdict);
    final icon = v.isGenuine
        ? Icons.verified_rounded
        : v.isFake
            ? Icons.dangerous_rounded
            : Icons.help_rounded;

    return Container(
      padding: const EdgeInsets.all(5),
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      child: Icon(icon, color: Colors.white, size: 14),
    );
  }
}
