import 'dart:math' show pi, cos, sin;
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../widgets/golden_sparkle.dart';

/// ============================================================================
/// RadarScreen — Deal Scanner (Screen 3 of 5)
/// ============================================================================
/// The center floating button screen featuring an animated radar visualization
/// that "scans" for deals across all platforms, plus a "Just Found" feed of
/// newly discovered deals.
///
/// Animations:
///   - Concentric circles: pulse 2s ease-in-out infinite, staggered 0.3s
///   - Sweep line: rotate 360deg, 3s, linear, infinite
///   - Radar dots: pulse 1.5s ease-in-out infinite, staggered
///   - Pulse dot: blink 1s infinite
///   - All driven by a single AnimationController via AnimatedBuilder
/// ============================================================================

class RadarScreen extends StatefulWidget {
  const RadarScreen({super.key});

  @override
  State<RadarScreen> createState() => _RadarScreenState();
}

class _RadarScreenState extends State<RadarScreen>
    with TickerProviderStateMixin {
  late final AnimationController _radarController;
  late final AnimationController _pulseController;

  // Demo deal data for "Just Found" section
  final List<Map<String, dynamic>> _justFoundDeals = [
    {
      'emoji': '\u{231A}',
      'title': 'Apple Watch Series 9',
      'price': 'EGP 9,999',
      'original': 'EGP 14,500',
      'source': 'Amazon',
      'sourceColor': AppColors.amazonOrange,
      'discount': '31%',
    },
    {
      'emoji': '\u{1F3A7}',
      'title': 'Sony WH-1000XM5',
      'price': 'EGP 5,999',
      'original': 'EGP 9,800',
      'source': 'Noon',
      'sourceColor': AppColors.noonYellow,
      'discount': '39%',
    },
    {
      'emoji': '\u{1F9F9}',
      'title': 'Dyson V15 Detect',
      'price': 'EGP 12,999',
      'original': 'EGP 22,000',
      'source': 'Jumia',
      'sourceColor': AppColors.jumiaOrange,
      'discount': '41%',
    },
  ];

  @override
  void initState() {
    super.initState();

    // Main radar controller: drives sweep rotation + all pulse timing
    _radarController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    )..repeat();

    // Secondary pulse controller for independent pulse timing (2s cycle)
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat();
  }

  @override
  void dispose() {
    _radarController.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GoldenSparkleBackground(
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 50, 20, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              // ═══════════════════════════════════════════════════════════════
              // HEADER
              // ═══════════════════════════════════════════════════════════════
              Text(
                'Deal Radar',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  color: const Color(0xFFFFF5E6), // textPrimary
                  letterSpacing: 0.5,
                  shadows: [
                    Shadow(
                      color: AppColors.emeraldGreen.withOpacity(0.3),
                      blurRadius: 12,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Scanning all platforms...',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFFB0B0C0), // textSecondary
                  letterSpacing: 0.3,
                ),
              ),

              const SizedBox(height: 32),

              // ═══════════════════════════════════════════════════════════════
              // RADAR VISUALIZATION
              // ═══════════════════════════════════════════════════════════════
              AnimatedBuilder(
                animation: Listenable.merge([_radarController, _pulseController]),
                builder: (context, child) {
                  return SizedBox(
                    width: 280,
                    height: 280,
                    child: CustomPaint(
                      size: const Size(280, 280),
                      painter: RadarPainter(
                        sweepAngle: _radarController.value * 2 * pi,
                        pulseValue: _pulseController.value,
                      ),
                    ),
                  );
                },
              ),

              const SizedBox(height: 24),

              // ═══════════════════════════════════════════════════════════════
              // STATUS BADGE
              // ═══════════════════════════════════════════════════════════════
              _buildStatusBadge(),

              const SizedBox(height: 32),

              // ═══════════════════════════════════════════════════════════════
              // JUST FOUND SECTION
              // ═══════════════════════════════════════════════════════════════
              _buildJustFoundHeader(),

              const SizedBox(height: 12),

              // Deal cards
              ...List.generate(
                _justFoundDeals.length,
                (index) => _buildDealCard(index),
              ),

              // Bottom safe area padding
              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // STATUS BADGE
  // ────────────────────────────────────────────────────────────────────────────
  Widget _buildStatusBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0x1400E676), // #1400E676
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: AppColors.emeraldGreen.withOpacity(0.2),
          width: 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Blinking pulse dot
          _buildBlinkingDot(),
          const SizedBox(width: 10),
          Text(
            'Last scan: 12 min ago \u{00B7} Next: 48 min',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: AppColors.emeraldGreen,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // BLINKING PULSE DOT
  // ────────────────────────────────────────────────────────────────────────────
  Widget _buildBlinkingDot() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        // Blink cycle: fade from 1.0 to 0.2 and back using sine wave
        final blinkPhase = sin(_pulseController.value * pi * 2);
        final opacity = (0.2 + 0.8 * ((1 + blinkPhase) / 2)).clamp(0.2, 1.0);

        return Opacity(
          opacity: opacity,
          child: Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: AppColors.emeraldGreen,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: AppColors.emeraldGreen.withOpacity(0.6),
                  blurRadius: 8,
                  spreadRadius: 1,
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // JUST FOUND HEADER
  // ────────────────────────────────────────────────────────────────────────────
  Widget _buildJustFoundHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Text(
              'Just Found',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: const Color(0xFFFFF5E6),
                letterSpacing: 0.3,
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: AppColors.emeraldGreen.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                '3 new',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: AppColors.emeraldGreen,
                ),
              ),
            ),
          ],
        ),
        TextButton(
          onPressed: () {
            // Navigate to all deals
          },
          style: TextButton.styleFrom(
            foregroundColor: AppColors.emeraldGreen,
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            minimumSize: Size.zero,
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
          child: const Text(
            'See All',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // DEAL CARD
  // ────────────────────────────────────────────────────────────────────────────
  Widget _buildDealCard(int index) {
    final deal = _justFoundDeals[index];

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF141420), // darkCard
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: const Color(0xFF1E1E2E).withOpacity(0.5),
          width: 1,
        ),
      ),
      child: Row(
        children: [
          // Emoji thumbnail
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: const Color(0xFF1E1E2E),
              borderRadius: BorderRadius.circular(12),
            ),
            alignment: Alignment.center,
            child: Text(
              deal['emoji'] as String,
              style: const TextStyle(fontSize: 28),
            ),
          ),
          const SizedBox(width: 14),

          // Deal info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Title
                Text(
                  deal['title'] as String,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFFFFF5E6),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 6),

                // Price row
                Row(
                  children: [
                    Text(
                      deal['price'] as String,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: AppColors.emeraldGreen,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      deal['original'] as String,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: Color(0xFF6E6E80),
                        decoration: TextDecoration.lineThrough,
                        decorationColor: Color(0xFF6E6E80),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),

                // Source badge + discount
                Row(
                  children: [
                    // Source badge
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: (deal['sourceColor'] as Color).withOpacity(0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        deal['source'] as String,
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: deal['sourceColor'] as Color,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),

                    // Discount badge
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.crimsonRed.withOpacity(0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        '-${deal['discount']}',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          color: AppColors.crimsonRed,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Arrow indicator
          Icon(
            Icons.chevron_right,
            color: const Color(0xFF6E6E80).withOpacity(0.5),
            size: 20,
          ),
        ],
      ),
    );
  }
}

/// ============================================================================
/// RadarPainter — CustomPainter for the animated radar visualization
/// ============================================================================
/// Draws:
///   - 4 concentric circles with staggered pulse animation
///   - Rotating sweep line with gradient
///   - 4 radar dots at pseudo-random positions with pulse
///   - Center dot with glow
/// ============================================================================

class RadarPainter extends CustomPainter {
  /// Current sweep angle in radians (0 to 2*pi)
  final double sweepAngle;

  /// Pulse value 0.0 to 1.0 from the pulse controller
  final double pulseValue;

  RadarPainter({
    required this.sweepAngle,
    required this.pulseValue,
  });

  // ─── Configuration ─────────────────────────────────────────────────────────

  /// Radar green color (primary accent)
  static const Color _radarGreen = Color(0xFF00E676);

  /// Number of concentric circles
  static const int _circleCount = 4;

  /// Number of radar dots
  static const int _dotCount = 4;

  /// Dot positions as normalized (x, y) offsets from center, -1 to 1 range
  /// These are "random-ish" but deterministic positions
  static final List<Offset> _dotPositions = [
    const Offset(0.35, -0.42),   // upper-right quadrant
    const Offset(-0.55, 0.25),   // lower-left quadrant
    const Offset(0.15, 0.60),    // bottom area
    const Offset(-0.30, -0.55),  // upper-left quadrant
  ];

  /// Stagger delays for each circle's pulse (as fraction of 2s cycle)
  static final List<double> _circleStagger = [0.0, 0.25, 0.5, 0.75];

  /// Stagger delays for each dot's pulse
  static final List<double> _dotStagger = [0.0, 0.33, 0.66, 0.15];

  // ─── Paint ─────────────────────────────────────────────────────────────────

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final maxRadius = size.width / 2;

    // Draw each concentric circle with staggered pulse
    for (int i = 0; i < _circleCount; i++) {
      _drawPulsingCircle(
        canvas,
        center: center,
        maxRadius: maxRadius,
        circleIndex: i,
        totalCircles: _circleCount,
      );
    }

    // Draw rotating sweep line
    _drawSweepLine(canvas, center, maxRadius);

    // Draw radar dots with staggered pulse
    for (int i = 0; i < _dotCount; i++) {
      _drawRadarDot(canvas, center, maxRadius, i);
    }

    // Draw center dot
    _drawCenterDot(canvas, center);
  }

  // ─── Concentric Circles ────────────────────────────────────────────────────

  void _drawPulsingCircle(
    Canvas canvas, {
    required Offset center,
    required double maxRadius,
    required int circleIndex,
    required int totalCircles,
  }) {
    // Base radius evenly distributed
    final baseRadius = maxRadius * (circleIndex + 1) / (totalCircles + 1);

    // Apply pulse: radius oscillates between 95% and 105% of base
    // Staggered by circle index
    final staggerOffset = _circleStagger[circleIndex];
    final pulsePhase = ((pulseValue + staggerOffset) % 1.0) * 2 * pi;
    final pulseFactor = 0.95 + 0.05 * (1 + sin(pulsePhase)) / 2;
    final radius = baseRadius * pulseFactor;

    // Opacity also pulses: 10% to 20%
    final opacityPulse = 0.10 + 0.10 * (1 + sin(pulsePhase)) / 2;

    final paint = Paint()
      ..color = _radarGreen.withOpacity(opacityPulse)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    canvas.drawCircle(center, radius, paint);
  }

  // ─── Sweep Line ────────────────────────────────────────────────────────────

  void _drawSweepLine(Canvas canvas, Offset center, double maxRadius) {
    // The sweep line extends from center to edge
    final lineLength = maxRadius * 0.92;

    // Draw the main sweep line with gradient-like effect using multiple segments
    // We draw from center outward with decreasing opacity for gradient effect
    const segmentCount = 40;
    for (int i = 0; i < segmentCount; i++) {
      final t1 = i / segmentCount;
      final t2 = (i + 1) / segmentCount;

      // Gradient: strong at center, fades toward tip
      // Use a curve that peaks near center and fades at edges
      final gradientAlpha = (1.0 - t1) * (1.0 - t1); // quadratic falloff
      final alpha = (0.05 + 0.75 * gradientAlpha).clamp(0.0, 1.0);

      final segStart = Offset(
        center.dx + lineLength * t1 * cos(sweepAngle),
        center.dy + lineLength * t1 * sin(sweepAngle),
      );
      final segEnd = Offset(
        center.dx + lineLength * t2 * cos(sweepAngle),
        center.dy + lineLength * t2 * sin(sweepAngle),
      );

      // Color shifts from bright green at center to transparent at edge
      // with a subtle glow in the middle
      final Color lineColor;
      if (t1 < 0.15) {
        // Bright green near center
        lineColor = const Color(0xFF00E676).withOpacity(alpha * 0.9);
      } else if (t1 < 0.6) {
        // Glowing section
        final glowIntensity = sin((t1 - 0.15) / 0.45 * pi);
        lineColor = const Color(0xCC00E676).withOpacity(alpha * glowIntensity);
      } else {
        // Fading to transparent
        lineColor = const Color(0x6600E676).withOpacity(alpha * 0.3);
      }

      final paint = Paint()
        ..color = lineColor
        ..strokeWidth = 2.0
        ..strokeCap = StrokeCap.round;

      canvas.drawLine(segStart, segEnd, paint);
    }

    // Draw a subtle glow triangle (radar "scan area") behind the sweep line
    _drawScanGlow(canvas, center, maxRadius);
  }

  // ─── Scan Glow (subtle cone behind sweep line) ─────────────────────────────

  void _drawScanGlow(Canvas canvas, Offset center, double maxRadius) {
    final scanRadius = maxRadius * 0.85;
    const scanAngle = pi / 4; // 45-degree scan cone

    // Create a gradient sweep from center outward
    final path = Path()
      ..moveTo(center.dx, center.dy)
      ..arcToPoint(
        Offset(
          center.dx + scanRadius * cos(sweepAngle + scanAngle),
          center.dy + scanRadius * sin(sweepAngle + scanAngle),
        ),
        radius: Radius.circular(scanRadius),
        largeArc: false,
      )
      ..lineTo(center.dx, center.dy);

    // Close the wedge path manually
    final wedgePath = Path()
      ..moveTo(center.dx, center.dy)
      ..lineTo(
        center.dx + scanRadius * cos(sweepAngle - scanAngle),
        center.dy + scanRadius * sin(sweepAngle - scanAngle),
      );

    // Draw arc segment
    for (int i = 0; i <= 20; i++) {
      final t = i / 20;
      final angle = sweepAngle - scanAngle + scanAngle * 2 * t;
      final point = Offset(
        center.dx + scanRadius * cos(angle),
        center.dy + scanRadius * sin(angle),
      );
      if (i == 0) {
        wedgePath.moveTo(
          center.dx + scanRadius * cos(sweepAngle - scanAngle),
          center.dy + scanRadius * sin(sweepAngle - scanAngle),
        );
      }
      wedgePath.lineTo(point.dx, point.y);
    }
    wedgePath.lineTo(center.dx, center.dy);
    wedgePath.close();

    // Fill with very subtle green gradient
    final gradient = RadialGradient(
      center: const Alignment(0, 0),
      radius: 1.0,
      colors: [
        const Color(0x1500E676),
        const Color(0x0500E676),
      ],
    );

    final paint = Paint()
      ..shader = gradient.createShader(
        Rect.fromCircle(center: center, radius: scanRadius),
      )
      ..style = PaintingStyle.fill;

    canvas.drawPath(wedgePath, paint);
  }

  // ─── Radar Dots ────────────────────────────────────────────────────────────

  void _drawRadarDot(
    Canvas canvas,
    Offset center,
    double maxRadius,
    int dotIndex,
  ) {
    final position = _dotPositions[dotIndex];
    final dotCenter = Offset(
      center.dx + position.dx * maxRadius * 0.75,
      center.dy + position.dy * maxRadius * 0.75,
    );

    // Staggered pulse for each dot
    final staggerOffset = _dotStagger[dotIndex];
    final pulsePhase = ((pulseValue + staggerOffset) % 1.0) * 2 * pi;
    final pulseScale = 1.0 + 0.25 * (1 + sin(pulsePhase)) / 2;
    final opacity = (0.6 + 0.4 * (1 + sin(pulsePhase)) / 2).clamp(0.4, 1.0);

    final dotSize = 5.0 * pulseScale; // base 5px radius (10px diameter)

    // Draw shadow/glow
    final shadowPaint = Paint()
      ..color = _radarGreen.withOpacity(0.6 * opacity)
      ..style = PaintingStyle.fill
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10);

    canvas.drawCircle(dotCenter, dotSize * 2, shadowPaint);

    // Draw dot
    final dotPaint = Paint()
      ..color = _radarGreen.withOpacity(opacity)
      ..style = PaintingStyle.fill;

    canvas.drawCircle(dotCenter, dotSize, dotPaint);
  }

  // ─── Center Dot ────────────────────────────────────────────────────────────

  void _drawCenterDot(Canvas canvas, Offset center) {
    const centerRadius = 8.0; // 16px diameter

    // Outer glow (20px blur)
    final glowPaint = Paint()
      ..color = _radarGreen.withOpacity(0.4)
      ..style = PaintingStyle.fill
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 20);

    canvas.drawCircle(center, centerRadius * 2.5, glowPaint);

    // Medium glow layer
    final mediumGlowPaint = Paint()
      ..color = _radarGreen.withOpacity(0.3)
      ..style = PaintingStyle.fill
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10);

    canvas.drawCircle(center, centerRadius * 1.5, mediumGlowPaint);

    // Core dot
    final corePaint = Paint()
      ..color = _radarGreen
      ..style = PaintingStyle.fill;

    canvas.drawCircle(center, centerRadius, corePaint);

    // Bright center highlight
    final highlightPaint = Paint()
      ..color = const Color(0xFF80FFAE) // lighter green
      ..style = PaintingStyle.fill;

    canvas.drawCircle(
      Offset(center.dx - 2, center.dy - 2),
      centerRadius * 0.4,
      highlightPaint,
    );
  }

  // ─── shouldRepaint ─────────────────────────────────────────────────────────

  @override
  bool shouldRepaint(covariant RadarPainter oldDelegate) {
    return oldDelegate.sweepAngle != sweepAngle ||
        oldDelegate.pulseValue != pulseValue;
  }
}
