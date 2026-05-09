/// ============================================================================
/// DealHunter Egypt — Home Screen (Complete Redesign)
/// ============================================================================
/// Emotional layout designed to trigger "DEAL HUNGER"
///
/// SECTIONS (top to bottom):
/// A. Header — Greeting + live deal counter with flame
/// B. Search Bar — Glassmorphism pill shape
/// C. Source Filter Chips — Amazon | Noon | Jumia
/// D. Category Chips — Icons with deal counts
/// E. Deal Cards — Glassmorphism with staggered animation
/// F. Floating Radar Button (in bottom nav)
/// ============================================================================

import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../widgets/deal_card.dart';
import '../widgets/custom_bottom_nav.dart';

class HomeScreen extends StatefulWidget {
  final String userName;
  final String userTier; // 'free', 'premium', 'vip'

  const HomeScreen({
    super.key,
    this.userName = 'Deals Hunter',
    this.userTier = 'free',
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with TickerProviderStateMixin {
  int _currentTab = 0;
  int _selectedSource = 0; // 0=All, 1=Amazon, 2=Noon, 3=Jumia
  String? _selectedCategory;
  late AnimationController _staggerController;

  // Demo data
  final int _liveDealsCount = 283;
  final List<String> _sources = ['All', 'Amazon', 'Noon', 'Jumia'];
  final List<Map<String, dynamic>> _categories = [
    {'name': 'Electronics', 'icon': Icons.phone_android, 'count': 89, 'slug': 'electronics'},
    {'name': 'Fashion', 'icon': Icons.shopping_bag, 'count': 67, 'slug': 'fashion'},
    {'name': 'Home', 'icon': Icons.chair, 'count': 45, 'slug': 'home'},
    {'name': 'Beauty', 'icon': Icons.spa, 'count': 47, 'slug': 'beauty'},
    {'name': 'Sports', 'icon': Icons.fitness_center, 'count': 23, 'slug': 'sports'},
    {'name': 'Toys', 'icon': Icons.toys, 'count': 18, 'slug': 'toys'},
    {'name': 'Food', 'icon': Icons.food_bank, 'count': 12, 'slug': 'grocery'},
    {'name': 'Auto', 'icon': Icons.directions_car, 'count': 8, 'slug': 'automotive'},
  ];

  @override
  void initState() {
    super.initState();
    _staggerController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );
    Future.delayed(const Duration(milliseconds: 200), () {
      if (mounted) _staggerController.forward();
    });
  }

  @override
  void dispose() {
    _staggerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.darkBackground,
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            // ── HEADER: Greeting + Live Counter ─────────────────────
            SliverToBoxAdapter(child: _buildHeader()),

            // ── SEARCH BAR ──────────────────────────────────────────
            SliverToBoxAdapter(child: _buildSearchBar()),

            // ── SOURCE FILTER CHIPS ─────────────────────────────────
            SliverToBoxAdapter(child: _buildSourceChips()),

            // ── CATEGORY CHIPS ──────────────────────────────────────
            SliverToBoxAdapter(child: _buildCategoryChips()),

            // ── SECTION TITLE: Featured Deals ───────────────────────
            SliverToBoxAdapter(child: _buildSectionTitle('Featured Deals')),

            // ── DEAL CARDS LIST ─────────────────────────────────────
            SliverPadding(
              padding: const EdgeInsets.only(bottom: 100),
              sliver: _buildDealCardsList(),
            ),
          ],
        ),
      ),

      // ── CUSTOM BOTTOM NAV with floating radar ───────────────────
      bottomNavigationBar: Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: CustomBottomNav(
          currentIndex: _currentTab,
          savedDealCount: 3,
          onTap: (index) => setState(() => _currentTab = index),
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // HEADER: Greeting + Live Deal Counter
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Greeting row: Avatar + Name
          Row(
            children: [
              // Avatar with tier glow ring
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(
                    colors: [
                      AppColors.tierColor(widget.userTier),
                      AppColors.tierColor(widget.userTier).withOpacity(0.6),
                    ],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.tierColor(widget.userTier).withOpacity(0.4),
                      blurRadius: 12,
                      spreadRadius: 2,
                    ),
                  ],
                ),
                child: Center(
                  child: Text(
                    widget.userName.isNotEmpty
                        ? widget.userName[0].toUpperCase()
                        : '?',
                    style: const TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              // Greeting text
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _greeting(),
                    style: const TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textSecondary,
                    ),
                  ),
                  Text(
                    widget.userName,
                    style: const TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ],
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Live deals counter with pulsing flame
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  AppColors.electricOrange.withOpacity(0.15),
                  AppColors.crimsonRed.withOpacity(0.08),
                ],
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: AppColors.electricOrange.withOpacity(0.2),
                width: 1,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Pulsing flame
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0.8, end: 1.2),
                  duration: const Duration(milliseconds: 800),
                  curve: Curves.easeInOut,
                  builder: (context, scale, child) {
                    return Transform.scale(
                      scale: scale,
                      child: child,
                    );
                  },
                  child: const Icon(
                    Icons.local_fire_department,
                    color: AppColors.electricOrange,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '$_liveDealsCount',
                  style: const TextStyle(
                    fontFamily: 'Inter',
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                    color: AppColors.electricOrange,
                  ),
                ),
                const SizedBox(width: 6),
                const Text(
                  'Live Deals Right Now',
                  style: TextStyle(
                    fontFamily: 'Inter',
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _greeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good Morning';
    if (hour < 17) return 'Good Afternoon';
    return 'Good Evening';
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // SEARCH BAR: Glassmorphism pill
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
      child: Container(
        height: 52,
        decoration: BoxDecoration(
          color: AppColors.darkSurface.withOpacity(0.8),
          borderRadius: BorderRadius.circular(28),
          border: Border.all(
            color: AppColors.glassBorder,
            width: 0.8,
          ),
          boxShadow: [
            BoxShadow(
              color: AppColors.deepPurple.withOpacity(0.06),
              blurRadius: 20,
              spreadRadius: -5,
            ),
          ],
        ),
        child: Row(
          children: [
            const SizedBox(width: 18),
            const Icon(Icons.search, color: AppColors.textMuted, size: 22),
            const SizedBox(width: 12),
            const Expanded(
              child: TextField(
                style: TextStyle(
                  fontFamily: 'Inter',
                  fontSize: 15,
                  color: AppColors.textPrimary,
                ),
                decoration: InputDecoration(
                  hintText: 'Search for your deal...',
                  hintStyle: TextStyle(
                    fontFamily: 'Inter',
                    fontSize: 15,
                    color: AppColors.textMuted,
                  ),
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ),
            // Filter button
            Container(
              margin: const EdgeInsets.all(6),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppColors.electricOrange, Color(0xFFFF8F00)],
                ),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Icon(
                Icons.tune,
                color: Colors.white,
                size: 18,
              ),
            ),
            const SizedBox(width: 6),
          ],
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // SOURCE FILTER CHIPS: All | Amazon | Noon | Jumia
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildSourceChips() {
    final sourceColors = [
      AppColors.deepPurple,
      AppColors.amazonOrange,
      AppColors.noonYellow,
      AppColors.jumiaOrange,
    ];

    return Container(
      height: 52,
      margin: const EdgeInsets.only(top: 8, bottom: 4),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        itemCount: _sources.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (context, index) {
          final isActive = _selectedSource == index;
          final color = sourceColors[index];

          return GestureDetector(
            onTap: () => setState(() => _selectedSource = index),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 250),
              curve: Curves.easeInOut,
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              decoration: BoxDecoration(
                color: isActive ? color : Colors.transparent,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(
                  color: isActive ? color : AppColors.glassBorder,
                  width: isActive ? 0 : 1.2,
                ),
                boxShadow: isActive
                    ? [
                        BoxShadow(
                          color: color.withOpacity(0.4),
                          blurRadius: 12,
                          spreadRadius: -2,
                        ),
                      ]
                    : null,
              ),
              child: Text(
                _sources[index],
                style: TextStyle(
                  fontFamily: 'Inter',
                  fontSize: 14,
                  fontWeight: isActive ? FontWeight.w700 : FontWeight.w500,
                  color: isActive
                      ? (index == 2 ? Colors.black : Colors.white)
                      : AppColors.textSecondary,
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // CATEGORY CHIPS: Icons with deal counts
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildCategoryChips() {
    return Container(
      height: 90,
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        itemCount: _categories.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (context, index) {
          final cat = _categories[index];
          final isSelected = _selectedCategory == cat['slug'];
          final catColor = AppColors.categoryColors[cat['slug']] ??
              AppColors.categoryColors['unknown']!;

          return GestureDetector(
            onTap: () {
              setState(() {
                _selectedCategory = isSelected ? null : cat['slug'] as String;
              });
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 250),
              width: 72,
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
              decoration: BoxDecoration(
                color: isSelected
                    ? catColor.withOpacity(0.3)
                    : catColor.withOpacity(0.12),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: isSelected
                      ? catColor.withOpacity(0.6)
                      : catColor.withOpacity(0.15),
                  width: 1.2,
                ),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    cat['icon'] as IconData,
                    size: 22,
                    color: isSelected
                        ? AppColors.textPrimary
                        : AppColors.textSecondary,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    cat['name'] as String,
                    style: TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 10,
                      fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                      color: isSelected
                          ? AppColors.textPrimary
                          : AppColors.textSecondary,
                    ),
                    textAlign: TextAlign.center,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${cat['count']} deals',
                    style: const TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 9,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textMuted,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // SECTION TITLE
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        children: [
          Text(
            title,
            style: const TextStyle(
              fontFamily: 'Inter',
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const Spacer(),
          TextButton(
            onPressed: () {},
            child: const Text(
              'See All',
              style: TextStyle(
                fontFamily: 'Inter',
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppColors.electricOrange,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // DEAL CARDS with staggered animation
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildDealCardsList() {
    // Demo deals
    final deals = [
      DealCardData(
        id: '1',
        title: 'Samsung Galaxy A15 6GB RAM, 128GB - Blue Black',
        imageUrl: 'https://images.unsplash.com/photo-1610945265078-3858a0b5d837?w=600',
        originalPrice: 6999,
        salePrice: 4199,
        discountPercent: 40,
        source: 'amazon_eg',
        category: 'electronics',
        trustStatus: 'genuine',
        productUrl: 'https://amazon.eg/dp/B0CNVXYLND',
        isNew: true,
        isFeatured: true,
      ),
      DealCardData(
        id: '2',
        title: 'Apple AirPods Pro 2nd Gen with USB-C',
        imageUrl: 'https://images.unsplash.com/photo-1603351154351-5cfb3d04ef32?w=600',
        originalPrice: 13999,
        salePrice: 7999,
        discountPercent: 43,
        source: 'noon_eg',
        category: 'electronics',
        trustStatus: 'genuine',
        productUrl: 'https://noon.com/egypt-en/apple-airpods-pro',
        isNew: true,
      ),
      DealCardData(
        id: '3',
        title: 'Nike Revolution 6 Running Shoes - Black/White',
        imageUrl: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600',
        originalPrice: 5499,
        salePrice: 2199,
        discountPercent: 60,
        source: 'jumia_eg',
        category: 'fashion',
        trustStatus: 'genuine',
        productUrl: 'https://jumia.com.eg/nike-revolution-6',
        isNew: false,
      ),
      DealCardData(
        id: '4',
        title: 'La Roche-Posay Cicaplast B5 Repairing Balm 100ml',
        imageUrl: 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=600',
        originalPrice: 899,
        salePrice: 539,
        discountPercent: 40,
        source: 'amazon_eg',
        category: 'beauty',
        trustStatus: 'genuine',
        productUrl: 'https://amazon.eg/larocheposay-cicaplast',
        isNew: true,
      ),
      DealCardData(
        id: '5',
        title: 'Essential XI Air Fryer 5.5L Digital - Black',
        imageUrl: 'https://images.unsplash.com/photo-1626147116986-4601771470a6?w=600',
        originalPrice: 5499,
        salePrice: 2749,
        discountPercent: 50,
        source: 'noon_eg',
        category: 'home',
        trustStatus: 'verified',
        productUrl: 'https://noon.com/egypt-en/air-fryer',
        isNew: true,
      ),
    ];

    return SliverList.builder(
      itemCount: deals.length,
      itemBuilder: (context, index) {
        // Staggered animation: each card delayed by 80ms
        final delay = index * 0.08;
        final animation = CurvedAnimation(
          parent: _staggerController,
          curve: Interval(
            delay.clamp(0.0, 0.8),
            (delay + 0.3).clamp(0.0, 1.0),
            curve: Curves.easeOutCubic,
          ),
        );

        return DealCard(
          deal: deals[index],
          fadeAnimation: animation,
          onTap: () {},
          onBuyTap: () {},
        );
      },
    );
  }
}
