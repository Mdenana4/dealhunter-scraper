import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../l10n/app_strings.dart';
import '../../models/deal_model.dart';
import '../../providers/app_providers.dart';
import '../../widgets/deal_widgets.dart';
import '../alerts/alerts_screen.dart';

class SavedScreen extends StatelessWidget {
  const SavedScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(context.s('saved_title')),
          bottom: TabBar(
            tabs: [
              Tab(icon: const Icon(Icons.bookmark_outline), text: context.s('tab_deals')),
              Tab(icon: const Icon(Icons.notifications_none), text: context.s('tab_alerts')),
            ],
          ),
        ),
        body: const TabBarView(
          children: [
            _SavedDealsTab(),
            AlertsScreen(),
          ],
        ),
      ),
    );
  }
}

class _SavedDealsTab extends ConsumerWidget {
  const _SavedDealsTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final savedIds = ref.watch(savedDealIdsProvider);
    final cs = Theme.of(context).colorScheme;

    return savedIds.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
      data: (ids) {
        if (ids.isEmpty) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.bookmark_outline,
                    size: 64, color: cs.onSurfaceVariant),
                const SizedBox(height: 12),
                Text(
                  context.s('no_saved'),
                  style: TextStyle(color: cs.onSurfaceVariant),
                ),
                const SizedBox(height: 8),
                Text(context.s('no_saved_hint')),
              ],
            ),
          );
        }
        return ListView.builder(
          itemCount: ids.length,
          itemBuilder: (_, i) => _SavedDealTile(dealId: ids[i]),
        );
      },
    );
  }
}

class _SavedDealTile extends ConsumerWidget {
  const _SavedDealTile({required this.dealId});

  final String dealId;

  Future<void> _unsave(BuildContext context, WidgetRef ref) async {
    final uid = ref.read(authStateProvider).valueOrNull?.uid;
    if (uid == null) return;
    await FirebaseFirestore.instance
        .collection('users')
        .doc(uid)
        .update({
      'saved_deals': FieldValue.arrayRemove([dealId]),
    });
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(context.s('removed_from_saved'))),
      );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dealAsync = ref.watch(dealDetailProvider(dealId));
    return dealAsync.when(
      loading: () => const ListTile(
        leading: SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(strokeWidth: 2)),
        title: Text('Loading...'),
      ),
      error: (_, __) => ListTile(
        leading: const Icon(Icons.error_outline),
        title: Text(dealId, overflow: TextOverflow.ellipsis),
        subtitle: const Text('Failed to load'),
      ),
      data: (deal) => Dismissible(
        key: Key(dealId),
        direction: DismissDirection.endToStart,
        background: Container(
          alignment: Alignment.centerRight,
          padding: const EdgeInsets.only(right: 20),
          color: Colors.red,
          child: const Icon(Icons.delete_outline, color: Colors.white),
        ),
        onDismissed: (_) => _unsave(context, ref),
        child: _DealRow(deal: deal),
      ),
    );
  }
}

class _DealRow extends StatelessWidget {
  const _DealRow({required this.deal});

  final DealModel deal;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: () => context.go('/home/deal/${deal.id}', extra: deal),
      leading: ClipRRect(
        borderRadius: BorderRadius.circular(6),
        child: SizedBox(
          width: 56,
          height: 56,
          child: deal.imageUrl.isNotEmpty
              ? Image.network(deal.imageUrl, fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) =>
                      const Icon(Icons.image_not_supported_outlined))
              : const Icon(Icons.image_outlined),
        ),
      ),
      title: Text(deal.title, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Row(
        children: [
          Text(
            deal.formattedPrice,
            style:
                TextStyle(color: Theme.of(context).colorScheme.primary),
          ),
          const SizedBox(width: 8),
          VerdictDot(verdict: deal.verdict),
        ],
      ),
      trailing: const Icon(Icons.chevron_right),
    );
  }
}
