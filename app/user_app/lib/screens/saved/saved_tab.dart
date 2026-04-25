import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/saved_provider.dart';
import '../../providers/auth_provider.dart';
import '../../config/theme.dart';
import '../../widgets/deal_card.dart';
import '../deals/deal_detail_screen.dart';

class SavedTab extends ConsumerWidget {
  const SavedTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(firebaseUserProvider).value;

    if (user == null) {
      return const _LoginPrompt();
    }

    final savedAsync = ref.watch(savedDealsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('💾 Saved Deals'),
        backgroundColor: AppTheme.primary,
      ),
      body: savedAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const Center(
            child: Text('Could not load saved deals.')),
        data: (deals) {
          if (deals.isEmpty) {
            return const _EmptySaved();
          }

          return RefreshIndicator(
            onRefresh: () => ref.refresh(savedDealsProvider.future),
            child: ListView.builder(
              itemCount: deals.length,
              itemBuilder: (ctx, i) {
                final deal = deals[i];
                return DealCard(
                  deal: deal,
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) => DealDetailScreen(deal: deal)),
                  ),
                  onSaveToggle: () async {
                    final actions = ref.read(savedActionsProvider);
                    if (actions == null) return;
                    await actions.unsave(deal.id);
                    ref.invalidate(savedDealsProvider);
                  },
                );
              },
            ),
          );
        },
      ),
    );
  }
}

class _EmptySaved extends StatelessWidget {
  const _EmptySaved();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.bookmark_border, size: 72, color: Colors.grey),
          const SizedBox(height: 16),
          Text('No saved deals yet',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text(
            'Tap the bookmark icon on any deal to save it here.',
            style: Theme.of(context)
                .textTheme
                .bodyMedium
                ?.copyWith(color: Colors.grey),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _LoginPrompt extends StatelessWidget {
  const _LoginPrompt();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.lock_outline, size: 72, color: Colors.grey),
            const SizedBox(height: 16),
            Text('Sign in to save deals',
                style: Theme.of(context).textTheme.headlineSmall,
                textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(
              'Create a free account to bookmark deals and track prices.',
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: Colors.grey),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () => Navigator.pushNamed(context, '/login'),
              child: const Text('Sign In / Register'),
            ),
          ],
        ),
      ),
    );
  }
}
