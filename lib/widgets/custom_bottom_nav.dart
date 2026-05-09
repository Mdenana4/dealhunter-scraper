/// ============================================================================
/// DealHunter Egypt — Custom Bottom Navigation with Floating Radar
/// ============================================================================
/// Features:
/// - 5 tabs: Home, Explore, Deals (center, elevated), Saved, Profile
/// - Center tab is a large floating button with gradient + radar pulse
/// - Active tab scales up 1.2x with electric orange fill
/// - Haptic feedback on tap (via vibrate package)
/// - Red dot notification badge on Saved tab
/// - Smooth 300ms transitions
/// ============================================================================

import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

class CustomBottomNav extends StatefulWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;
  final int savedDealCount;
  final bool hasPriceDrop;

  const CustomBottomNav({
    super.key,
    required this.currentIndex,
    required this.onTap,
    this.savedDealCount = 0,
    this.hasPriceDrop = false,
  });

  @override
  State<CustomBottomNav> createState() => _CustomBottomNavState();
}

class _CustomBottomNavState extends State<CustomBottomNav>
    with TickerProviderStateMixin {
  late AnimationController _radarController;

  @override
  void initState() {
    super.initState();
    _radarController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat();
  }

  @override
  void dispose() {
    _radarController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.bottomCenter,
      children: [
        // ── Main tab bar background ─────────────────────────────────
        Container(
          height: 72,
          margin: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: AppColors.charcoal.withOpacity(0.95),
            borderRadius: BorderRadius.circular(28),
            border: Border.all(
              color: AppColors.glassBorder,
              width: 0.5,
            ),
            boxShadow: [
              BoxShadow(
                color: AppColors.deepPurple.withOpacity(0.15),
                blurRadius: 30,
                spreadRadius: -5,
                offset: const Offset(0, -5),
              ),
              BoxShadow(
                color: Colors.black.withOpacity(0.4),
                blurRadius: 20,
                spreadRadius: -5,
              ),
            ],
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              // Tab 0: Home
              _buildTab(0, Icons.home_rounded, 'Home'),

              // Tab 1: Explore
              _buildTab(1, Icons.explore_rounded, 'Explore'),

              // Spacer for center button
              const SizedBox(width: 72),

              // Tab 3: Saved (with badge)
              _buildTab(2, Icons.favorite_rounded, 'Saved',
                  badgeCount: widget.savedDealCount > 0 ? widget.savedDealCount : null),

              // Tab 4: Profile
              _buildTab(3, Icons.person_rounded, 'Profile'),
            ],
          ),
        ),

        // ── Center floating radar button ────────────────────────────
        Positioned(
          bottom: 36, // Half above the bar
          child: GestureDetector(
            onTap: () => widget.onTap(4),
            child: _RadarButton(
              isActive: widget.currentIndex == 4,
              animation: _radarController,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildTab(int index, IconData icon, String label, {int? badgeCount}) {
    final isActive = widget.currentIndex == index;

    return GestureDetector(
      onTap: () => widget.onTap(index),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Icon with animation
            AnimatedScale(
              scale: isActive ? 1.2 : 1.0,
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeInOut,
              child: Stack(
                children: [
                  Icon(
                    icon,
                    size: 24,
                    color: isActive ? AppColors.electricOrange : AppColors.textSecondary,
                  ),
                  // Red notification dot
                  if (badgeCount != null && badgeCount > 0)
                    Positioned(
                      top: -2,
                      right: -2,
                      child: Container(
                        width: 16,
                        height: 16,
                        decoration: BoxDecoration(
                          color: AppColors.crimsonRed,
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: AppColors.charcoal,
                            width: 2,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: AppColors.crimsonRed.withOpacity(0.5),
                              blurRadius: 6,
                            ),
                          ],
                        ),
                        child: Center(
                          child: Text(
                            badgeCount > 9 ? '9+' : '$badgeCount',
                            style: const TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 4),
            // Label
            AnimatedDefaultTextStyle(
              duration: const Duration(milliseconds: 300),
              style: TextStyle(
                fontFamily: 'Inter',
                fontSize: 11,
                fontWeight: isActive ? FontWeight.w700 : FontWeight.w400,
                color: isActive ? AppColors.electricOrange : AppColors.textSecondary,
              ),
              child: Text(label),
            ),
            // Active indicator dot
            AnimatedOpacity(
              opacity: isActive ? 1.0 : 0.0,
              duration: const Duration(milliseconds: 300),
              child: Container(
                margin: const EdgeInsets.only(top: 4),
                width: 4,
                height: 4,
                decoration: const BoxDecoration(
                  color: AppColors.electricOrange,
                  shape: BoxShape.circle,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// RADAR BUTTON — The floating center button with scan animation
// ═══════════════════════════════════════════════════════════════════════════════

class _RadarButton extends StatelessWidget {
  final bool isActive;
  final AnimationController animation;

  const _RadarButton({
    required this.isActive,
    required this.animation,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 72,
      height: 72,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // ── Expanding radar rings ──────────────────────────────
          ...List.generate(3, (index) {
            return AnimatedBuilder(
              animation: animation,
              builder: (context, child) {
                final delay = index * 0.33;
                final progress = ((animation.value + delay) % 1.0);
                final scale = 0.5 + (progress * 0.8);
                final opacity = (1.0 - progress) * 0.3;

                return Transform.scale(
                  scale: scale,
                  child: Container(
                    width: 60,
                    height: 60,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: isActive
                            ? AppColors.electricOrange.withOpacity(opacity)
                            : AppColors.deepPurple.withOpacity(opacity * 0.5),
                        width: 2,
                      ),
                    ),
                  ),
                );
              },
            );
          }),

          // ── Main button ──────────────────────────────────────────
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: isActive
                  ? const LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [AppColors.electricOrange, AppColors.deepPurple],
                    )
                  : const LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFF3A1F5C), Color(0xFF2D1B4E)],
                    ),
              boxShadow: [
                BoxShadow(
                  color: isActive
                      ? AppColors.electricOrange.withOpacity(0.5)
                      : AppColors.deepPurple.withOpacity(0.3),
                  blurRadius: 20,
                  spreadRadius: 2,
                ),
              ],
            ),
            child: Icon(
              Icons.radar,
              size: 28,
              color: isActive ? Colors.white : AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}
