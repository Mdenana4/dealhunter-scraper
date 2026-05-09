/// ============================================================================
/// DealHunter Egypt — Color Psychology System
/// ============================================================================
/// Every color is chosen to trigger "DEAL HUNGER" — the irresistible urge
/// to find discounts and save money.
///
/// INSPIRATION: McDonald's color psychology
/// - Yellow = Happiness, optimism, attention  →  GOLDEN_YELLOW for savings
/// - Red    = Appetite, urgency, excitement   →  ELECTRIC_ORANGE + CRIMSON for BUY NOW
///
/// FRAMEWORK: Flutter 3.x+ Dark Mode Default
/// ============================================================================

import 'package:flutter/material.dart';

class AppColors {
  AppColors._(); // private constructor — prevent instantiation

  // ═══════════════════════════════════════════════════════════════════════════
  // PRIMARY — Urgency & Excitement (BUY NOW trigger)
  // ═══════════════════════════════════════════════════════════════════════════
  /// Electric Orange — The BUY NOW color.
  /// Psychology: Creates urgency, excitement, impulse. Used for primary
  /// CTAs, discount badges, floating action buttons.
  /// McDonald's parallel: The red that makes you hungry — but for deals.
  static const Color electricOrange = Color(0xFFFF6B00);

  /// Deep Purple — Premium, exclusive, VIP status.
  /// Psychology: Conveys luxury, exclusivity, "this deal is special."
  /// Used for VIP tier accents, premium badges, gradients.
  static const Color deepPurple = Color(0xFF6C00FF);

  // ═══════════════════════════════════════════════════════════════════════════
  // TRUST — Safety & Verification
  // ═══════════════════════════════════════════════════════════════════════════
  /// Emerald Green — Trust, verified, safe to buy.
  /// Psychology: "This deal is GENUINE." Used for verified badges,
  /// genuine indicators, success states, trust signals.
  static const Color emeraldGreen = Color(0xFF00E676);

  /// Soft Green — Subtle trust, used for backgrounds of trust elements.
  static const Color softGreen = Color(0xFF00C853);

  // ═══════════════════════════════════════════════════════════════════════════
  // WARNING — Fake Deals & Caution
  // ═══════════════════════════════════════════════════════════════════════════
  /// Crimson Red — Fake deals, scam alerts, limited time warnings.
  /// Psychology: Danger, stop, warning. Used for fake deal badges,
  /// scam alerts, error states.
  static const Color crimsonRed = Color(0xFFFF1744);

  /// Amber — Suspicious deals, caution.
  /// Psychology: "Be careful." Used for suspicious/needs-verification badges.
  static const Color amberWarning = Color(0xFFFFB300);

  // ═══════════════════════════════════════════════════════════════════════════
  // SAVINGS — Money, Value, Reward
  // ═══════════════════════════════════════════════════════════════════════════
  /// Golden Yellow — Savings, money, value, reward.
  /// Psychology: "You're SAVING money!" Used for savings amounts,
  /// price reductions, reward badges, coin animations.
  /// McDonald's parallel: The yellow arches — happiness from saving.
  static const Color goldenYellow = Color(0xFFFFD700);

  /// Gold shimmer — For premium/flash deal effects.
  static const Color goldShimmer = Color(0xFFFFE066);

  // ═══════════════════════════════════════════════════════════════════════════
  // BACKGROUNDS — Dark Mode System
  // ═══════════════════════════════════════════════════════════════════════════
  /// Ultra-dark background — Main app background.
  /// Psychology: Premium, cinematic, easy on eyes at night.
  /// Lets deal images and discount colors POP.
  static const Color darkBackground = Color(0xFF0A0A0F);

  /// Slightly lighter dark — Card backgrounds, elevated surfaces.
  static const Color darkCard = Color(0xFF141420);

  /// Dark surface — Input fields, secondary cards.
  static const Color darkSurface = Color(0xFF1E1E2E);

  /// Charcoal — Tab bar, bottom nav background.
  static const Color charcoal = Color(0xFF1A1A2E);

  // ═══════════════════════════════════════════════════════════════════════════
  // GLASSMORPHISM
  // ═══════════════════════════════════════════════════════════════════════════
  /// Glass white — For glassmorphism card backgrounds.
  static const Color glassWhite = Color(0x18FFFFFF); // ~10% opacity white

  /// Glass border — Subtle border on glass cards.
  static const Color glassBorder = Color(0x30FFFFFF); // ~20% opacity white

  // ═══════════════════════════════════════════════════════════════════════════
  // TEXT — Contrast Hierarchy
  // ═══════════════════════════════════════════════════════════════════════════
  /// Primary text — Headlines, deal titles.
  static const Color textPrimary = Color(0xFFFFF5E6); // Warm white

  /// Secondary text — Descriptions, meta info.
  static const Color textSecondary = Color(0xFFB0B0C0); // Soft gray

  /// Muted text — Timestamps, hints.
  static const Color textMuted = Color(0xFF6E6E80);

  /// Cream white — For clean, honest, trustworthy sections.
  static const Color creamWhite = Color(0xFFFFF0F0);

  // ═══════════════════════════════════════════════════════════════════════════
  // GRADIENTS — Pre-built for common use
  // ═══════════════════════════════════════════════════════════════════════════
  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [electricOrange, deepPurple],
  );

  static const LinearGradient discountGradientLow = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [Color(0xFFFF8F00), electricOrange],
  );

  static const LinearGradient discountGradientHigh = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [electricOrange, crimsonRed],
  );

  static const LinearGradient discountGradientExtreme = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [goldenYellow, electricOrange, crimsonRed, deepPurple],
  );

  // ═══════════════════════════════════════════════════════════════════════════
  // BRAND COLORS — Source Badges
  // ═══════════════════════════════════════════════════════════════════════════
  static const Color amazonOrange = Color(0xFFFF9900);
  static const Color noonYellow = Color(0xFFF7C600);
  static const Color noonPurple = Color(0xFF6C00FF);
  static const Color jumiaOrange = Color(0xFFF68B1E);

  // ═══════════════════════════════════════════════════════════════════════════
  // TIER COLORS — User subscription levels
  // ═══════════════════════════════════════════════════════════════════════════
  static const Color tierFree = Color(0xFF9E9E9E);     // Gray
  static const Color tierPremium = Color(0xFFFFD700);   // Gold
  static const Color tierVIP = Color(0xFF6C00FF);       // Purple

  // ═══════════════════════════════════════════════════════════════════════════
  // CATEGORY COLORS — Soft pastels for category chips
  // ═══════════════════════════════════════════════════════════════════════════
  static const Map<String, Color> categoryColors = {
    'electronics': Color(0xFF1E3A5F),
    'fashion': Color(0xFF5E2D4E),
    'home': Color(0xFF2D5E3E),
    'beauty': Color(0xFF5E2D5E),
    'sports': Color(0xFF3E4A2D),
    'toys': Color(0xFF5E4A2D),
    'grocery': Color(0xFF4A2D3E),
    'automotive': Color(0xFF3E2D2D),
    'books': Color(0xFF2D3E5E),
    'unknown': Color(0xFF3E3E4A),
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // HELPERS
  // ═══════════════════════════════════════════════════════════════════════════

  /// Get gradient for a discount percentage.
  static LinearGradient discountGradient(int percent) {
    if (percent >= 80) return discountGradientExtreme;
    if (percent >= 60) return discountGradientHigh;
    return discountGradientLow;
  }

  /// Get color for trust/fake status.
  static Color trustColor(String status) {
    switch (status.toLowerCase()) {
      case 'genuine':
      case 'verified':
        return emeraldGreen;
      case 'suspicious':
      case 'needs_verification':
        return amberWarning;
      case 'fake':
      case 'scam':
        return crimsonRed;
      default:
        return textMuted;
    }
  }

  /// Get glow color for source badge.
  static Color sourceGlow(String source) {
    if (source.contains('amazon')) return amazonOrange.withOpacity(0.4);
    if (source.contains('noon')) return noonYellow.withOpacity(0.4);
    if (source.contains('jumia')) return jumiaOrange.withOpacity(0.4);
    return electricOrange.withOpacity(0.4);
  }

  /// Get tier color.
  static Color tierColor(String tier) {
    switch (tier.toLowerCase()) {
      case 'premium': return tierPremium;
      case 'vip': return tierVIP;
      default: return tierFree;
    }
  }
}
