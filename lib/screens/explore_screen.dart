import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';

/// Explore / Discovery tab (Screen 2 of 5)
/// Lets users browse categories, popular stores, and trending deals.
class ExploreScreen extends StatefulWidget {
  const ExploreScreen({super.key});

  @override
  State<ExploreScreen> createState() => _ExploreScreenState();
}

class _ExploreScreenState extends State<ExploreScreen>
    with TickerProviderStateMixin {
  late final AnimationController _staggerController;

  // Active store chip index (none by default)
  int _activeStoreIndex = -1;

  // Active category index (none by default)
  int _activeCategoryIndex = -1;

  // ── demo data ───────────────────────────────────────────────
  final List<Map<String, dynamic>> _stores = const [
    {'name': 'Amazon Egypt', 'icon': Icons.shopping_bag},
    {'name': 'Noon', 'icon': Icons.wb_sunny},
    {'name': 'Jumia', 'icon': Icons.shopping_cart},
  ];

  final List<Map<String, String>> _categories = const [
    {'emoji': '📱', 'label': 'Phones'},
    {'emoji': '💻', 'label': 'Laptops'},
    {'emoji': '🎧', 'label': 'Audio'},
    {'emoji': '📺', 'label': 'TVs'},
    {'emoji': '👕', 'label': 'Fashion'},
    {'emoji': '🏠', 'label': 'Home'},
    {'emoji': '🎮', 'label': 'Gaming'},
    {'emoji': '💄', 'label': 'Beauty'},
    {'emoji': '⚽', 'label': 'Sports'},
  ];

  final List<Map<String, dynamic>> _trending = const [
    {'name': 'iPhone 15 Pro', 'discount': 42},
    {'name': 'Samsung S24', 'discount': 38},
    {'name': 'AirPods Pro 2', 'discount': 45},
    {'name': 'PlayStation 5', 'discount': 33},
    {'name': 'Dyson Airwrap', 'discount': 51},
    {'name': 'Ninja Blender', 'discount': 47},
  ];

  // ── lifecycle ───────────────────────────────────────────────
  @override
  void initState() {
    super.initState();
    _staggerController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    Future.delayed(const Duration(milliseconds: 120), () {
      if (mounted) _staggerController.forward();
    });
  }

  @override
  void dispose() {
    _staggerController.dispose();
    super.dispose();
  }

  // ── stagger helper ──────────────────────────────────────────
  Animation<double> _sectionAnimation(int index) {
    final double begin = (index * 80) / 900; // 80 ms per section
    final double end = begin + 0.35;
    return CurvedAnimation(
      parent: _staggerController,
      curve: Interval(
        begin.clamp(0.0, 1.0),
        end.clamp(0.0, 1.0),
        curve: Curves.easeOutCubic,
      ),
    );
  }

  // ── build ───────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.darkBackground,
      body: SafeArea(
        top: false,
        bottom: false,
        child: CustomScrollView(
          physics: const BouncingScrollPhysics(),
          slivers: [
            // ── status-bar padding ──
            SliverToBoxAdapter(
              child: SizedBox(height: MediaQuery.of(context).padding.top + 16),
            ),

            // ── header ──
            SliverToBoxAdapter(
              child: FadeTransition(
                opacity: _sectionAnimation(0),
                child: SlideTransition(
                  position: Tween<Offset>(
                    begin: const Offset(0, 0.18),
                    end: Offset.zero,
                  ).animate(_sectionAnimation(0)),
                  child: _buildHeader(),
                ),
              ),
            ),

            // ── search bar ──
            SliverToBoxAdapter(
              child: FadeTransition(
                opacity: _sectionAnimation(1),
                child: SlideTransition(
                  position: Tween<Offset>(
                    begin: const Offset(0, 0.18),
                    end: Offset.zero,
                  ).animate(_sectionAnimation(1)),
                  child: _buildSearchBar(),
                ),
              ),
            ),

            // ── popular stores ──
            SliverToBoxAdapter(
              child: FadeTransition(
                opacity: _sectionAnimation(2),
                child: SlideTransition(
                  position: Tween<Offset>(
                    begin: const Offset(0, 0.18),
                    end: Offset.zero,
                  ).animate(_sectionAnimation(2)),
                  child: _buildPopularStores(),
                ),
              ),
            ),

            // ── browse categories ──
            SliverToBoxAdapter(
              child: FadeTransition(
                opacity: _sectionAnimation(3),
                child: SlideTransition(
                  position: Tween<Offset>(
                    begin: const Offset(0, 0.18),
                    end: Offset.zero,
                  ).animate(_sectionAnimation(3)),
                  child: _buildCategories(),
                ),
              ),
            ),

            // ── trending now ──
            SliverToBoxAdapter(
              child: FadeTransition(
                opacity: _sectionAnimation(4),
                child: SlideTransition(
                  position: Tween<Offset>(
                    begin: const Offset(0, 0.18),
                    end: Offset.zero,
                  ).animate(_sectionAnimation(4)),
                  child: _buildTrending(),
                ),
              ),
            ),

            // ── bottom safe-area + bottom-nav clearance ──
            SliverToBoxAdapter(
              child: SizedBox(
                height: MediaQuery.of(context).padding.bottom + 80,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ═════════════════════════════════════════════════════════════
  //  HEADER
  // ═════════════════════════════════════════════════════════════
  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.only(
        top: 50,
        left: 20,
        right: 20,
        bottom: 20,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            'Explore',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
              letterSpacing: -0.3,
              height: 1.2,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Discover deals across all categories',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: AppColors.textSecondary,
              height: 1.3,
            ),
          ),
        ],
      ),
    );
  }

  // ═════════════════════════════════════════════════════════════
  //  SEARCH BAR
  // ═════════════════════════════════════════════════════════════
  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: GestureDetector(
        onTap: () {
          // TODO: Navigate to search screen
        },
        child: Container(
          height: 52,
          decoration: BoxDecoration(
            color: const Color(0xFF1E1E2E).withOpacity(0.8),
            borderRadius: BorderRadius.circular(28),
            border: Border.all(
              color: const Color(0x30FFFFFF),
              width: 0.8,
            ),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            children: [
              Icon(
                Icons.search,
                color: AppColors.textSecondary,
                size: 20,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  'Search categories, brands...',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: AppColors.textSecondary,
                  ),
                ),
              ),
              Icon(
                Icons.tune,
                color: AppColors.textSecondary,
                size: 18,
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ═════════════════════════════════════════════════════════════
  //  POPULAR STORES
  // ═════════════════════════════════════════════════════════════
  Widget _buildPopularStores() {
    return Padding(
      padding: const EdgeInsets.only(top: 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section title
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Text(
              'Popular Stores',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
                letterSpacing: -0.2,
              ),
            ),
          ),
          const SizedBox(height: 14),
          // Horizontal chip list
          SizedBox(
            height: 44,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 20),
              itemCount: _stores.length,
              separatorBuilder: (_, __) => const SizedBox(width: 10),
              itemBuilder: (context, index) {
                final store = _stores[index];
                final isActive = _activeStoreIndex == index;
                return GestureDetector(
                  onTap: () {
                    setState(() {
                      _activeStoreIndex = isActive ? -1 : index;
                    });
                  },
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 220),
                    curve: Curves.easeOutCubic,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: isActive
                          ? const Color(0x19FF6B00)
                          : const Color(0x05FFFFFF),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(
                        color: isActive
                            ? const Color(0x30FF6B00)
                            : const Color(0x08FFFFFF),
                        width: 1,
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          store['icon'] as IconData,
                          color: isActive
                              ? const Color(0xFFFF6B00)
                              : AppColors.textSecondary,
                          size: 18,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          store['name'] as String,
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: isActive
                                ? const Color(0xFFFF6B00)
                                : AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  // ═════════════════════════════════════════════════════════════
  //  BROWSE CATEGORIES (3-column grid)
  // ═════════════════════════════════════════════════════════════
  Widget _buildCategories() {
    return Padding(
      padding: const EdgeInsets.only(top: 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section title
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Text(
              'Browse Categories',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
                letterSpacing: -0.2,
              ),
            ),
          ),
          const SizedBox(height: 14),
          // Category grid
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.0,
              ),
              itemCount: _categories.length,
              itemBuilder: (context, index) {
                final cat = _categories[index];
                final isActive = _activeCategoryIndex == index;
                return GestureDetector(
                  onTap: () {
                    setState(() {
                      _activeCategoryIndex = isActive ? -1 : index;
                    });
                  },
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 220),
                    curve: Curves.easeOutCubic,
                    transform: isActive
                        ? (Matrix4.identity()..translate(0.0, -3.0))
                        : Matrix4.identity(),
                    decoration: BoxDecoration(
                      color: isActive
                          ? const Color(0x10FF6B00)
                          : const Color(0x04FFFFFF),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: isActive
                            ? const Color(0x20FF6B00)
                            : const Color(0x06FFFFFF),
                        width: 1,
                      ),
                    ),
                    padding: const EdgeInsets.symmetric(
                      vertical: 18,
                      horizontal: 8,
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          cat['emoji']!,
                          style: const TextStyle(fontSize: 28),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          cat['label']!,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textSecondary,
                            height: 1.2,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  // ═════════════════════════════════════════════════════════════
  //  TRENDING NOW
  // ═════════════════════════════════════════════════════════════
  Widget _buildTrending() {
    return Padding(
      padding: const EdgeInsets.only(top: 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section title
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Text(
              'Trending Now 🔥',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
                letterSpacing: -0.2,
              ),
            ),
          ),
          const SizedBox(height: 14),
          // Trending list
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Column(
              children: List.generate(_trending.length, (index) {
                final item = _trending[index];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _buildTrendingItem(
                    rank: index + 1,
                    name: item['name'] as String,
                    discount: item['discount'] as int,
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTrendingItem({
    required int rank,
    required String name,
    required int discount,
  }) {
    // Gold for rank 1-2, orange for rank 3+
    final rankColor = rank <= 2 ? const Color(0xFFFFD700) : const Color(0xFFFF6B00);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: const Color(0x03FFFFFF),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: const Color(0x05FFFFFF),
          width: 0.5,
        ),
      ),
      child: Row(
        children: [
          // Rank number
          SizedBox(
            width: 32,
            child: Text(
              '$rank',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: rankColor,
              ),
            ),
          ),
          const SizedBox(width: 4),
          // Product name
          Expanded(
            child: Text(
              name,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          // Discount badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: const Color(0xFF00E676).withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              '-$discount%',
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: Color(0xFF00E676),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
