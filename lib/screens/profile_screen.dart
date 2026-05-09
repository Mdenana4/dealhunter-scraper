import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../widgets/golden_sparkle.dart';

/// Profile Screen — Screen 5 of 5 (DealHunter Egypt)
/// User profile with VIP badge, stats, settings menu, and logout.
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen>
    with TickerProviderStateMixin {
  late final AnimationController _staggerController;
  late final List<Animation<double>> _fadeAnimations;
  late final List<Animation<Offset>> _slideAnimations;
  late final AnimationController _shimmerController;

  final List<_MenuSection> _menuSections = const [
    _MenuSection(
      title: 'Account',
      items: [
        _MenuItem(
          emoji: '\uD83D\uDD14',
          title: 'Notifications',
          subtitle: 'Price alerts, deal reminders',
        ),
        _MenuItem(
          emoji: '\uD83C\uDFAF',
          title: 'Preferences',
          subtitle: 'Categories, brands, locations',
        ),
        _MenuItem(
          emoji: '\uD83C\uDFEA',
          title: 'Stores',
          subtitle: 'Amazon, Noon, Jumia, Carrefour',
        ),
      ],
    ),
    _MenuSection(
      title: 'App',
      items: [
        _MenuItem(
          emoji: '\uD83C\uDF19',
          title: 'Appearance',
          subtitle: 'Dark mode always on',
        ),
        _MenuItem(
          emoji: '\uD83C\uDF0D',
          title: 'Language',
          subtitle: 'English / \u0627\u0644\u0639\u0631\u0628\u064A\u0629',
        ),
        _MenuItem(
          emoji: '\u2753',
          title: 'Help & Support',
          subtitle: 'FAQ, contact us, report a bug',
        ),
        _MenuItem(
          emoji: '\uD83D\uDCCB',
          title: 'About',
          subtitle: 'Version 2.0.1',
        ),
      ],
    ),
  ];

  @override
  void initState() {
    super.initState();

    // Staggered entrance controller
    _staggerController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );

    // Shimmer controller for VIP badge
    _shimmerController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    )..repeat();

    // Build staggered animations for 8 elements (header + stats + 2 sections + logout)
    const int itemCount = 8;
    _fadeAnimations = List.generate(itemCount, (i) {
      final start = i * 0.08;
      final end = start + 0.35;
      return Tween<double>(begin: 0.0, end: 1.0).animate(
        CurvedAnimation(
          parent: _staggerController,
          curve: Interval(start.clamp(0.0, 1.0), end.clamp(0.0, 1.0),
              curve: Curves.easeOut),
        ),
      );
    });

    _slideAnimations = List.generate(itemCount, (i) {
      final start = i * 0.08;
      final end = start + 0.35;
      return Tween<Offset>(
        begin: const Offset(0, 18),
        end: Offset.zero,
      ).animate(
        CurvedAnimation(
          parent: _staggerController,
          curve: Interval(start.clamp(0.0, 1.0), end.clamp(0.0, 1.0),
              curve: Curves.easeOutCubic),
        ),
      );
    });

    // Kick off entrance
    _staggerController.forward();
  }

  @override
  void dispose() {
    _staggerController.dispose();
    _shimmerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.darkBackground,
      body: SafeArea(
        bottom: false,
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.only(bottom: 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Header with Golden Sparkles ──
              _buildHeader(),

              // ── Stats Row ──
              _buildStatsRow(),

              const SizedBox(height: 8),

              // ── Settings Menu: Section 1 (Account) ──
              _buildSectionWrapper(2, _buildMenuSection(_menuSections[0])),

              const SizedBox(height: 16),

              // ── Settings Menu: Section 2 (App) ──
              _buildSectionWrapper(3, _buildMenuSection(_menuSections[1])),

              const SizedBox(height: 24),

              // ── Log Out Button ──
              _buildLogoutButton(),

              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  HEADER
  // ═══════════════════════════════════════════════════════════════
  Widget _buildHeader() {
    return AnimatedBuilder(
      animation: _staggerController,
      builder: (context, child) {
        return FadeTransition(
          opacity: _fadeAnimations[0],
          child: Transform.translate(
            offset: _slideAnimations[0].value,
            child: child,
          ),
        );
      },
      child: GoldenSparkleBackground(
        intensity: SparkleIntensity.high,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.electricOrange.withOpacity(0.25),
            AppColors.darkCard.withOpacity(0.4),
          ],
        ),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(20, 50, 20, 30),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Avatar
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: const LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      Color(0xFFFF6B00),
                      Color(0xFFFF8533),
                    ],
                  ),
                  border: Border.all(
                    color: const Color(0x30FF6B00),
                    width: 3,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFFFF6B00).withOpacity(0.20),
                      blurRadius: 20,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: const Center(
                  child: Icon(
                    Icons.person,
                    size: 36,
                    color: Colors.white,
                  ),
                ),
              ),

              const SizedBox(height: 14),

              // Name
              Text(
                'Ahmed Hassan',
                style: AppTheme.textStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),

              const SizedBox(height: 4),

              // Email
              Text(
                'ahmed.hassan@email.com',
                style: AppTheme.textStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w400,
                  color: AppColors.textSecondary,
                ),
              ),

              const SizedBox(height: 14),

              // VIP Member Badge with Shimmer
              _buildVipBadge(),
            ],
          ),
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  VIP BADGE (with shimmer sweep)
  // ═══════════════════════════════════════════════════════════════
  Widget _buildVipBadge() {
    return AnimatedBuilder(
      animation: _shimmerController,
      builder: (context, child) {
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Color(0xFFFF6B00),
                Color(0xFFFF8533),
              ],
            ),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFFFF6B00).withOpacity(0.25),
                blurRadius: 12,
                offset: const Offset(0, 3),
              ),
            ],
          ),
          child: ShaderMask(
            shaderCallback: (bounds) {
              final slide = _shimmerController.value;
              return LinearGradient(
                begin: Alignment(-1.5 + slide * 3.0, 0),
                end: Alignment(-0.5 + slide * 3.0, 0),
                colors: const [
                  Colors.white,
                  Color(0xFFFFF5A0),
                  Colors.white,
                ],
                stops: const [0.0, 0.5, 1.0],
              ).createShader(bounds);
            },
            blendMode: BlendMode.srcATop,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  '\uD83D\uDC51',
                  style: TextStyle(fontSize: 16),
                ),
                const SizedBox(width: 6),
                Text(
                  'VIP MEMBER',
                  style: AppTheme.textStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                    letterSpacing: 0.8,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  STATS ROW
  // ═══════════════════════════════════════════════════════════════
  Widget _buildStatsRow() {
    return AnimatedBuilder(
      animation: _staggerController,
      builder: (context, child) {
        return FadeTransition(
          opacity: _fadeAnimations[1],
          child: Transform.translate(
            offset: _slideAnimations[1].value,
            child: child,
          ),
        );
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
        padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
        decoration: BoxDecoration(
          color: const Color(0x02FFFFFF),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: const Color(0x05FFFFFF),
            width: 1,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: const [
            _StatItem(value: '47', label: 'Deals Saved'),
            _StatDivider(),
            _StatItem(value: 'EGP 12K', label: 'Potential Savings'),
            _StatDivider(),
            _StatItem(value: '23', label: 'Shared'),
          ],
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  MENU SECTION
  // ═══════════════════════════════════════════════════════════════
  Widget _buildMenuSection(_MenuSection section) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Section title
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
          child: Text(
            section.title.toUpperCase(),
            style: AppTheme.textStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: AppColors.textMuted,
              letterSpacing: 1.2,
            ),
          ),
        ),
        // Section card
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: AppColors.darkCard,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: const Color(0x05FFFFFF),
              width: 1,
            ),
          ),
          child: Column(
            children: List.generate(section.items.length, (index) {
              final item = section.items[index];
              final isLast = index == section.items.length - 1;
              return _MenuListItem(
                emoji: item.emoji,
                title: item.title,
                subtitle: item.subtitle,
                showBorder: !isLast,
              );
            }),
          ),
        ),
      ],
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  SECTION WRAPPER with stagger
  // ═══════════════════════════════════════════════════════════════
  Widget _buildSectionWrapper(int index, Widget child) {
    return AnimatedBuilder(
      animation: _staggerController,
      builder: (context, _) {
        return FadeTransition(
          opacity: _fadeAnimations[index],
          child: Transform.translate(
            offset: _slideAnimations[index].value,
            child: child,
          ),
        );
      },
      child: child,
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  LOGOUT BUTTON
  // ═══════════════════════════════════════════════════════════════
  Widget _buildLogoutButton() {
    return AnimatedBuilder(
      animation: _staggerController,
      builder: (context, child) {
        return FadeTransition(
          opacity: _fadeAnimations[7],
          child: Transform.translate(
            offset: _slideAnimations[7].value,
            child: child,
          ),
        );
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: GestureDetector(
          onTapDown: (_) {},
          child: _LogoutButton(
            onTap: () => _showLogoutDialog(context),
          ),
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  LOGOUT DIALOG
  // ═══════════════════════════════════════════════════════════════
  void _showLogoutDialog(BuildContext context) {
    showDialog(
      context: context,
      barrierColor: Colors.black.withOpacity(0.6),
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.darkCard,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: Color(0x08FFFFFF), width: 1),
        ),
        title: Text(
          'Log Out',
          style: AppTheme.textStyle(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: AppColors.textPrimary,
          ),
        ),
        content: Text(
          'Are you sure you want to log out of your account?',
          style: AppTheme.textStyle(
            fontSize: 14,
            fontWeight: FontWeight.w400,
            color: AppColors.textSecondary,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(
              'Cancel',
              style: AppTheme.textStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.textMuted,
              ),
            ),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              // Perform logout
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(
                    'Logged out successfully',
                    style: AppTheme.textStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                    ),
                  ),
                  backgroundColor: AppColors.darkCard,
                  behavior: SnackBarBehavior.floating,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  duration: const Duration(seconds: 2),
                ),
              );
            },
            child: Text(
              'Log Out',
              style: AppTheme.textStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: const Color(0xFFFF4757),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  STAT ITEM WIDGET
// ═══════════════════════════════════════════════════════════════════
class _StatItem extends StatelessWidget {
  final String value;
  final String label;

  const _StatItem({required this.value, required this.label});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: AppTheme.textStyle(
            fontSize: 20,
            fontWeight: FontWeight.w800,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: AppTheme.textStyle(
            fontSize: 11,
            fontWeight: FontWeight.w500,
            color: const Color(0xFF666666),
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  STAT DIVIDER
// ═══════════════════════════════════════════════════════════════════
class _StatDivider extends StatelessWidget {
  const _StatDivider();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 1,
      height: 36,
      color: const Color(0x10FFFFFF),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  MENU LIST ITEM (interactive with hover + tap feedback)
// ═══════════════════════════════════════════════════════════════════
class _MenuListItem extends StatefulWidget {
  final String emoji;
  final String title;
  final String subtitle;
  final bool showBorder;

  const _MenuListItem({
    required this.emoji,
    required this.title,
    required this.subtitle,
    this.showBorder = true,
  });

  @override
  State<_MenuListItem> createState() => _MenuListItemState();
}

class _MenuListItemState extends State<_MenuListItem>
    with SingleTickerProviderStateMixin {
  bool _isHovered = false;
  late final AnimationController _tapController;
  late final Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _tapController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 120),
    );
    _scaleAnimation = Tween<double>(begin: 1.0, end: 0.98).animate(
      CurvedAnimation(parent: _tapController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _tapController.dispose();
    super.dispose();
  }

  void _onTapDown(TapDownDetails _) {
    _tapController.forward();
  }

  void _onTapUp(TapUpDetails _) {
    _tapController.reverse();
    _onTap();
  }

  void _onTapCancel() {
    _tapController.reverse();
  }

  void _onTap() {
    // Placeholder tap action — navigate or show coming soon
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          '${widget.title} — Coming soon',
          style: AppTheme.textStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: Colors.white,
          ),
        ),
        backgroundColor: AppColors.darkCard,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        duration: const Duration(seconds: 1),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: _onTapDown,
      onTapUp: _onTapUp,
      onTapCancel: _onTapCancel,
      child: MouseRegion(
        onEnter: (_) => setState(() => _isHovered = true),
        onExit: (_) => setState(() => _isHovered = false),
        child: AnimatedBuilder(
          animation: _scaleAnimation,
          builder: (context, child) {
            return Transform.scale(
              scale: _scaleAnimation.value,
              child: child,
            );
          },
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOutCubic,
            padding: EdgeInsets.only(
              left: _isHovered ? 18 : 14,
              right: 14,
              top: 14,
              bottom: 14,
            ),
            decoration: BoxDecoration(
              border: widget.showBorder
                  ? const Border(
                      bottom: BorderSide(
                        color: Color(0x04FFFFFF),
                        width: 1,
                      ),
                    )
                  : null,
            ),
            child: Row(
              children: [
                // Icon circle
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0x05FFFFFF),
                  ),
                  child: Center(
                    child: Text(
                      widget.emoji,
                      style: const TextStyle(fontSize: 18),
                    ),
                  ),
                ),
                const SizedBox(width: 14),
                // Title + subtitle
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.title,
                        style: AppTheme.textStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        widget.subtitle,
                        style: AppTheme.textStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w400,
                          color: AppColors.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
                // Arrow
                Text(
                  '\u203A',
                  style: AppTheme.textStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w300,
                    color: const Color(0xFF444444),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  LOGOUT BUTTON
// ═══════════════════════════════════════════════════════════════════
class _LogoutButton extends StatefulWidget {
  final VoidCallback onTap;

  const _LogoutButton({required this.onTap});

  @override
  State<_LogoutButton> createState() => _LogoutButtonState();
}

class _LogoutButtonState extends State<_LogoutButton>
    with SingleTickerProviderStateMixin {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onTap();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeInOut,
        transform: Matrix4.identity()..scale(_pressed ? 0.97 : 1.0),
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: const Color(0x19FF4757),
          border: Border.all(
            color: const Color(0x20FF4757),
            width: 1,
          ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Center(
          child: Text(
            'Log Out',
            style: AppTheme.textStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: const Color(0xFFFF4757),
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  DATA CLASSES
// ═══════════════════════════════════════════════════════════════════
class _MenuItem {
  final String emoji;
  final String title;
  final String subtitle;

  const _MenuItem({
    required this.emoji,
    required this.title,
    required this.subtitle,
  });
}

class _MenuSection {
  final String title;
  final List<_MenuItem> items;

  const _MenuSection({required this.title, required this.items});
}
