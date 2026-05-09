/// ============================================================================
/// DealHunter Egypt — Glassmorphism Deal Card
/// ============================================================================
/// The hero widget. Every pixel is designed to trigger "DEAL HUNGER."
///
/// FEATURES:
/// - Glassmorphism card with subtle purple glow
/// - Animated discount badge (pulse speed increases with %)
/// - Source badge (Amazon/Noon/Jumia) with brand color ring
/// - Trust indicator (Genuine/Suspicious/Fake/Unverified)
/// - Savings calculation with Golden Yellow highlight
/// - Staggered fade-in on scroll
/// - Confetti trigger for 50%+ discounts
///
/// EMOTIONAL TRIGGERS:
/// - Urgency: Pulsing discount badge
/// - Trust: Green glow ring for verified deals
/// - Excitement: Confetti on 50%+ deals
/// - Exclusivity: Glassmorphism = premium feel
/// ============================================================================

import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

/// Data model for a deal — adapt to your existing Deal model
class DealCardData {
  final String id;
  final String title;
  final String? description;
  final String imageUrl;
  final double originalPrice;
  final double salePrice;
  final double discountPercent;
  final String currency;
  final String source; // 'amazon_eg', 'noon_eg', 'jumia_eg'
  final String category;
  final String? trustStatus; // 'genuine', 'suspicious', 'fake', null
  final String productUrl;
  final bool isNew;
  final bool isFeatured;

  const DealCardData({
    required this.id,
    required this.title,
    this.description,
    required this.imageUrl,
    required this.originalPrice,
    required this.salePrice,
    required this.discountPercent,
    this.currency = 'EGP',
    required this.source,
    required this.category,
    this.trustStatus,
    required this.productUrl,
    this.isNew = false,
    this.isFeatured = false,
  });

  double get savings => originalPrice - salePrice;
  String get sourceLabel {
    if (source.contains('amazon')) return 'Amazon';
    if (source.contains('noon')) return 'Noon';
    if (source.contains('jumia')) return 'Jumia';
    return 'DealHunter';
  }

  Color get sourceColor {
    if (source.contains('amazon')) return AppColors.amazonOrange;
    if (source.contains('noon')) return AppColors.noonYellow;
    if (source.contains('jumia')) return AppColors.jumiaOrange;
    return AppColors.electricOrange;
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// DEAL CARD WIDGET
// ═══════════════════════════════════════════════════════════════════════════════

class DealCard extends StatefulWidget {
  final DealCardData deal;
  final VoidCallback? onTap;
  final VoidCallback? onBuyTap;
  final Animation<double>? fadeAnimation;

  const DealCard({
    super.key,
    required this.deal,
    this.onTap,
    this.onBuyTap,
    this.fadeAnimation,
  });

  @override
  State<DealCard> createState() => _DealCardState();
}

class _DealCardState extends State<DealCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  bool _showConfetti = false;

  @override
  void initState() {
    super.initState();
    // Pulse speed: faster = bigger discount
    final pulseDuration = widget.deal.discountPercent >= 80
        ? 600
        : widget.deal.discountPercent >= 60
            ? 900
            : 1400;

    _pulseController = AnimationController(
      vsync: this,
      duration: Duration(milliseconds: pulseDuration),
    )..repeat(reverse: true);

    // Trigger confetti for 50%+ deals on first build
    if (widget.deal.discountPercent >= 50 && widget.deal.isNew) {
      Future.delayed(const Duration(milliseconds: 300), () {
        if (mounted) setState(() => _showConfetti = true);
      });
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final deal = widget.deal;
    final discount = deal.discountPercent.round();

    Widget card = GestureDetector(
      onTap: widget.onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: _cardDecoration(deal),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: Stack(
            children: [
              // ── Main content ──────────────────────────────────────────
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Image section
                  _buildImageSection(deal),
                  // Info section
                  _buildInfoSection(deal, discount),
                ],
              ),

              // ── Overlays ─────────────────────────────────────────────
              // Source badge (top-left)
              Positioned(
                top: 12,
                left: 12,
                child: _SourceBadge(deal: deal),
              ),

              // Discount badge (top-right, pulsing)
              Positioned(
                top: 12,
                right: 12,
                child: _DiscountBadge(
                  discount: discount,
                  animation: _pulseController,
                ),
              ),

              // "NEW" badge (below discount)
              if (deal.isNew)
                Positioned(
                  top: 56,
                  right: 12,
                  child: _NewBadge(),
                ),

              // Confetti overlay (50%+)
              if (_showConfetti)
                Positioned.fill(
                  child: _ConfettiOverlay(
                    onComplete: () => setState(() => _showConfetti = false),
                  ),
                ),
            ],
          ),
        ),
      ),
    );

    // Apply fade animation if provided
    if (widget.fadeAnimation != null) {
      card = FadeTransition(
        opacity: widget.fadeAnimation!,
        child: SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0, 0.15),
            end: Offset.zero,
          ).animate(widget.fadeAnimation!),
          child: card,
        ),
      );
    }

    return card;
  }

  // ── Card decoration with source-colored glow ───────────────────────────
  BoxDecoration _cardDecoration(DealCardData deal) {
    return BoxDecoration(
      borderRadius: BorderRadius.circular(20),
      color: AppColors.darkCard.withOpacity(0.85),
      border: Border.all(
        color: deal.sourceColor.withOpacity(0.25),
        width: 1,
      ),
      boxShadow: [
        // Source color glow
        BoxShadow(
          color: deal.sourceColor.withOpacity(0.15),
          blurRadius: 20,
          spreadRadius: -5,
          offset: const Offset(0, 10),
        ),
        // Deep purple ambient
        BoxShadow(
          color: AppColors.deepPurple.withOpacity(0.08),
          blurRadius: 40,
          spreadRadius: -10,
          offset: const Offset(0, 20),
        ),
      ],
    );
  }

  // ── Image section ──────────────────────────────────────────────────────
  Widget _buildImageSection(DealCardData deal) {
    return Stack(
      children: [
        // Product image
        ClipRRect(
          borderRadius: const BorderRadius.vertical(
            top: Radius.circular(20),
          ),
          child: AspectRatio(
            aspectRatio: 16 / 9,
            child: Image.network(
              deal.imageUrl,
              fit: BoxFit.cover,
              loadingBuilder: (context, child, progress) {
                if (progress == null) return child;
                return Container(
                  color: AppColors.darkSurface,
                  child: const Center(
                    child: CircularProgressIndicator(
                      color: AppColors.electricOrange,
                      strokeWidth: 2,
                    ),
                  ),
                );
              },
              errorBuilder: (context, error, stack) => Container(
                color: AppColors.darkSurface,
                child: const Icon(
                  Icons.image_not_supported_outlined,
                  color: AppColors.textMuted,
                  size: 48,
                ),
              ),
            ),
          ),
        ),

        // Subtle gradient overlay at bottom for text readability
        Positioned(
          bottom: 0,
          left: 0,
          right: 0,
          height: 60,
          child: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Colors.transparent,
                  AppColors.darkCard.withOpacity(0.8),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  // ── Info section ───────────────────────────────────────────────────────
  Widget _buildInfoSection(DealCardData deal, int discount) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title
          Text(
            deal.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontFamily: AppTheme.fontFamily,
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
              height: 1.35,
            ),
          ),

          const SizedBox(height: 12),

          // Price row
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              // Current price
              Text(
                '${deal.salePrice.toStringAsFixed(0)}',
                style: const TextStyle(
                  fontFamily: AppTheme.fontFamily,
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                deal.currency,
                style: const TextStyle(
                  fontFamily: AppTheme.fontFamily,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(width: 10),
              // Original price (crossed out)
              Text(
                '${deal.originalPrice.toStringAsFixed(0)} ${deal.currency}',
                style: const TextStyle(
                  fontFamily: AppTheme.fontFamily,
                  fontSize: 13,
                  fontWeight: FontWeight.w400,
                  color: AppColors.textMuted,
                  decoration: TextDecoration.lineThrough,
                  decorationColor: AppColors.crimsonRed,
                ),
              ),
            ],
          ),

          const SizedBox(height: 6),

          // Savings row
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.goldenYellow.withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              'Save ${deal.currency} ${deal.savings.toStringAsFixed(0)}',
              style: const TextStyle(
                fontFamily: AppTheme.fontFamily,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: AppColors.goldenYellow,
              ),
            ),
          ),

          const SizedBox(height: 12),

          // Bottom row: Trust badge + Buy button
          Row(
            children: [
              // Trust badge
              if (deal.trustStatus != null)
                _TrustBadge(status: deal.trustStatus!)
              else
                _TrustBadge(status: 'unverified'),

              const Spacer(),

              // Buy Now button
              _BuyNowButton(onTap: widget.onBuyTap),
            ],
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// SOURCE BADGE — Amazon / Noon / Jumia
// ═══════════════════════════════════════════════════════════════════════════════

class _SourceBadge extends StatelessWidget {
  final DealCardData deal;

  const _SourceBadge({required this.deal});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.darkBackground.withOpacity(0.85),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: deal.sourceColor.withOpacity(0.5),
          width: 1.2,
        ),
        boxShadow: [
          BoxShadow(
            color: deal.sourceColor.withOpacity(0.3),
            blurRadius: 8,
            spreadRadius: -2,
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Colored dot
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: deal.sourceColor,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: deal.sourceColor.withOpacity(0.5),
                  blurRadius: 6,
                ),
              ],
            ),
          ),
          const SizedBox(width: 6),
          Text(
            deal.sourceLabel,
            style: const TextStyle(
              fontFamily: AppTheme.fontFamily,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// DISCOUNT BADGE — Animated pulse
// ═══════════════════════════════════════════════════════════════════════════════

class _DiscountBadge extends StatelessWidget {
  final int discount;
  final AnimationController animation;

  const _DiscountBadge({
    required this.discount,
    required this.animation,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: animation,
      builder: (context, child) {
        final scale = 1.0 + (animation.value * 0.06);
        final glowIntensity = 0.3 + (animation.value * 0.3);

        return Transform.scale(
          scale: scale,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              gradient: AppColors.discountGradient(discount),
              borderRadius: BorderRadius.circular(14),
              boxShadow: [
                BoxShadow(
                  color: AppColors.electricOrange.withOpacity(glowIntensity),
                  blurRadius: 12 + (animation.value * 8),
                  spreadRadius: -2,
                ),
              ],
            ),
            child: Text(
              '-$discount%',
              style: const TextStyle(
                fontFamily: AppTheme.fontFamily,
                fontSize: 14,
                fontWeight: FontWeight.w900,
                color: Colors.white,
                letterSpacing: -0.5,
              ),
            ),
          ),
        );
      },
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// NEW BADGE — Slides in from right
// ═══════════════════════════════════════════════════════════════════════════════

class _NewBadge extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 400),
      curve: Curves.elasticOut,
      builder: (context, value, child) {
        return Transform.scale(
          scale: value,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: AppColors.emeraldGreen,
              borderRadius: BorderRadius.circular(10),
              boxShadow: [
                BoxShadow(
                  color: AppColors.emeraldGreen.withOpacity(0.4),
                  blurRadius: 8,
                ),
              ],
            ),
            child: const Text(
              'NEW',
              style: TextStyle(
                fontFamily: AppTheme.fontFamily,
                fontSize: 10,
                fontWeight: FontWeight.w900,
                color: Colors.white,
              ),
            ),
          ),
        );
      },
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRUST BADGE — Genuine / Suspicious / Fake / Unverified
// ═══════════════════════════════════════════════════════════════════════════════

class _TrustBadge extends StatelessWidget {
  final String status;

  const _TrustBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    final color = AppColors.trustColor(status);

    IconData icon;
    String label;
    switch (status.toLowerCase()) {
      case 'genuine':
      case 'verified':
        icon = Icons.verified_outlined;
        label = 'GENUINE';
        break;
      case 'suspicious':
        icon = Icons.warning_amber_outlined;
        label = 'CHECK';
        break;
      case 'fake':
        icon = Icons.block_outlined;
        label = 'FAKE';
        break;
      default:
        icon = Icons.help_outline;
        label = 'CHECK';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.4), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontFamily: AppTheme.fontFamily,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// BUY NOW BUTTON — Electric Orange with glow
// ═══════════════════════════════════════════════════════════════════════════════

class _BuyNowButton extends StatelessWidget {
  final VoidCallback? onTap;

  const _BuyNowButton({this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [AppColors.electricOrange, Color(0xFFFF8F00)],
          ),
          borderRadius: BorderRadius.circular(14),
          boxShadow: [
            BoxShadow(
              color: AppColors.electricOrange.withOpacity(0.4),
              blurRadius: 12,
              spreadRadius: -2,
            ),
          ],
        ),
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Buy Now',
              style: TextStyle(
                fontFamily: AppTheme.fontFamily,
                fontSize: 12,
                fontWeight: FontWeight.w800,
                color: Colors.white,
              ),
            ),
            SizedBox(width: 4),
            Icon(Icons.arrow_forward, size: 12, color: Colors.white),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// CONFETTI OVERLAY — Celebration for 50%+ deals
// ═══════════════════════════════════════════════════════════════════════════════

class _ConfettiOverlay extends StatefulWidget {
  final VoidCallback onComplete;

  const _ConfettiOverlay({required this.onComplete});

  @override
  State<_ConfettiOverlay> createState() => _ConfettiOverlayState();
}

class _ConfettiOverlayState extends State<_ConfettiOverlay>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    );
    _controller.forward().then((_) => widget.onComplete());
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween<double>(begin: 1, end: 0).animate(
        CurvedAnimation(parent: _controller, curve: const Interval(0.5, 1)),
      ),
      child: IgnorePointer(
        child: Center(
          child: Icon(
            Icons.celebration,
            size: 80,
            color: AppColors.goldenYellow.withOpacity(0.3),
          ),
        ),
      ),
    );
  }
}

// Required import for AppTheme reference
class AppTheme {
  static const String fontFamily = 'Inter';
}
