import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';

// ─── Demo Saved Deal Model ───────────────────────────────────────────────────

class _SavedDeal {
  final int id;
  final String emoji;
  final String title;
  final double currentPrice;
  final double oldPrice;
  final String source;
  final double? dropPercent; // null = no drop

  const _SavedDeal({
    required this.id,
    required this.emoji,
    required this.title,
    required this.currentPrice,
    required this.oldPrice,
    required this.source,
    this.dropPercent,
  });

  bool get hasDrop => dropPercent != null && dropPercent! > 0;
}

// ─── SavedScreen ─────────────────────────────────────────────────────────────

class SavedScreen extends StatefulWidget {
  final List<int> savedDealIds;

  const SavedScreen({
    super.key,
    this.savedDealIds = const [],
  });

  @override
  State<SavedScreen> createState() => SavedScreenState();
}

// NOTE: State class is PUBLIC so main.dart can access it via GlobalKey.
class SavedScreenState extends State<SavedScreen>
    with TickerProviderStateMixin {
  // ── Tabs ──
  int _activeTab = 0; // 0 = Wishlist, 1 = Price Drops

  // ── Demo Data ──
  final List<_SavedDeal> _allDeals = const [
    _SavedDeal(
      id: 1,
      emoji: '\u{1F4F1}',
      title: 'iPhone 15 Pro',
      currentPrice: 42999,
      oldPrice: 48500,
      source: 'AMAZON.EG',
      dropPercent: 11,
    ),
    _SavedDeal(
      id: 2,
      emoji: '\u{1F4BB}',
      title: 'MacBook Air M3',
      currentPrice: 28500,
      oldPrice: 32900,
      source: 'NOON',
    ),
    _SavedDeal(
      id: 3,
      emoji: '\u{1F3A7}',
      title: 'Galaxy Buds3 Pro',
      currentPrice: 3299,
      oldPrice: 4800,
      source: 'JUMIA',
      dropPercent: 31,
    ),
    _SavedDeal(
      id: 4,
      emoji: '\u{1F4FA}',
      title: 'LG OLED TV',
      currentPrice: 24999,
      oldPrice: 35000,
      source: 'AMAZON.EG',
    ),
    _SavedDeal(
      id: 5,
      emoji: '\u{1F3A7}',
      title: 'Sony WH-1000XM5',
      currentPrice: 5499,
      oldPrice: 8850,
      source: 'NOON',
    ),
  ];

  late List<_SavedDeal> _wishlistDeals;

  // Track which items are being removed for exit animation
  final Set<int> _removingIds = {};

  @override
  void initState() {
    super.initState();
    _wishlistDeals = List.from(_allDeals);
  }

  // ── Helpers ──

  List<_SavedDeal> get _priceDropDeals =>
      _wishlistDeals.where((d) => d.hasDrop).toList();

  List<_SavedDeal> get _visibleDeals =>
      _activeTab == 0 ? _wishlistDeals : _priceDropDeals;

  // ── Remove with animation ──

  Future<void> _removeDeal(int id) async {
    setState(() => _removingIds.add(id));
    await Future.delayed(const Duration(milliseconds: 350));
    setState(() {
      _wishlistDeals.removeWhere((d) => d.id == id);
      _removingIds.remove(id);
    });
  }

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ─── Header ───
            _buildHeader(),

            // ─── Toggle Tabs ───
            _buildToggleTabs(),

            // ─── Content ───
            Expanded(
              child: _visibleDeals.isEmpty ? _buildEmptyState() : _buildList(),
            ),

            // Bottom safe area padding
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  //  HEADER
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildHeader() {
    final dealCount = _wishlistDeals.length;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 50, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title
          const Text(
            'Saved Deals',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w700,
              color: Color(0xFFFFF5E6),
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          // Subtitle with dynamic count
          Text(
            '$dealCount deal${dealCount == 1 ? '' : 's'} saved',
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w400,
              color: Color(0xFFB0B0C0),
            ),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  //  TOGGLE TABS
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildToggleTabs() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _buildTabButton('Wishlist', 0),
          const SizedBox(width: 8),
          _buildTabButton('Price Drops', 1),
        ],
      ),
    );
  }

  Widget _buildTabButton(String label, int index) {
    final isActive = _activeTab == index;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeInOutCubic,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      decoration: BoxDecoration(
        color: isActive
            ? const Color(0x19FF6B00) // active bg
            : const Color(0x05FFFFFF), // inactive bg
        borderRadius: BorderRadius.circular(20),
        border: isActive
            ? Border.all(color: const Color(0x30FF6B00), width: 1)
            : null,
      ),
      child: GestureDetector(
        onTap: () => setState(() => _activeTab = index),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: isActive
                ? const Color(0xFFFF6B00) // active text
                : const Color(0xFF888888), // inactive text
          ),
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  //  LIST (Wishlist / Price Drops)
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildList() {
    final deals = _visibleDeals;
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      itemCount: deals.length,
      itemBuilder: (context, index) {
        final deal = deals[index];
        final isRemoving = _removingIds.contains(deal.id);

        return AnimatedContainer(
          duration: const Duration(milliseconds: 350),
          curve: Curves.easeInOutCubic,
          transform: isRemoving
              ? (Matrix4.identity()..translate(-200.0, 0.0))
              : Matrix4.identity(),
          child: AnimatedOpacity(
            duration: const Duration(milliseconds: 350),
            opacity: isRemoving ? 0.0 : 1.0,
            child: Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _buildSavedCard(deal),
            ),
          ),
        );
      },
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  //  SAVED DEAL CARD
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildSavedCard(_SavedDeal deal) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0x04FFFFFF),
        border: Border.all(color: const Color(0x06FFFFFF), width: 1),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          // ── Emoji Thumbnail ──
          Container(
            width: 70,
            height: 70,
            decoration: BoxDecoration(
              color: const Color(0x08FFFFFF),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: Text(
                deal.emoji,
                style: const TextStyle(fontSize: 32),
              ),
            ),
          ),
          const SizedBox(width: 14),

          // ── Info Column ──
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Title
                Text(
                  deal.title,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFFFFF5E6),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 6),

                // Price Row: current + old (strikethrough)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      'EGP ${_formatPrice(deal.currentPrice)}',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'EGP ${_formatPrice(deal.oldPrice)}',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w400,
                        color: Color(0xFF666666),
                        decoration: TextDecoration.lineThrough,
                        decorationColor: Color(0xFF666666),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),

                // ── Badges Row ──
                Row(
                  children: [
                    // Source badge
                    Text(
                      deal.source,
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF888888),
                        letterSpacing: 0.5,
                      ),
                    ),
                    // Price drop badge (if applicable)
                    if (deal.hasDrop) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: const Color(0x0800E676),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          'dropped ${deal.dropPercent!.toStringAsFixed(0)}%',
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF00E676),
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),

          // ── Heart / Remove Button ──
          GestureDetector(
            onTap: () => _removeDeal(deal.id),
            child: Container(
              width: 32,
              height: 32,
              decoration: const BoxDecoration(
                color: Color(0x19FF4757),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.favorite,
                color: Color(0xFFFF4757),
                size: 16,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  //  EMPTY STATE
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildEmptyState() {
    final isPriceDropsTab = _activeTab == 1;

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 40),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Large heart icon
            Icon(
              isPriceDropsTab ? Icons.trending_down : Icons.favorite_border,
              size: 64,
              color: const Color(0xFF333333),
            ),
            const SizedBox(height: 20),

            // Title
            Text(
              isPriceDropsTab
                  ? 'No price drops yet'
                  : 'No saved deals yet',
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: Color(0xFF888888),
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),

            // Subtitle
            Text(
              isPriceDropsTab
                  ? 'Save deals to track price drops automatically'
                  : 'Tap the heart on any deal to save it',
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w400,
                color: Color(0xFF666666),
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 28),

            // CTA Button
            GestureDetector(
              onTap: () {
                // Navigate to deals screen (index 0)
                // Consumer code in main.dart will handle this
              },
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 32,
                  vertical: 14,
                ),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [
                      Color(0xFFFF6B00),
                      Color(0xFFFF8C00),
                    ],
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                  ),
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Text(
                  isPriceDropsTab ? 'Set Alert' : 'Browse Deals',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  //  UTILITIES
  // ═══════════════════════════════════════════════════════════════════════════

  String _formatPrice(double price) {
    // Format with comma separators for thousands
    return price.toStringAsFixed(0).replaceAllMapped(
          RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
          (match) => '${match[1]},',
        );
  }
}
