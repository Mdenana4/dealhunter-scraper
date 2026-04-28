import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../l10n/app_strings.dart';
import '../../providers/app_providers.dart';

class AlertsScreen extends ConsumerWidget {
  const AlertsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final alertsAsync = ref.watch(userAlertsProvider);
    final cs = Theme.of(context).colorScheme;

    return alertsAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: cs.error),
            const SizedBox(height: 12),
            Text(context.s('failed_alerts'), style: TextStyle(color: cs.error)),
            const SizedBox(height: 8),
            TextButton(
              onPressed: () => ref.invalidate(userAlertsProvider),
              child: Text(context.s('retry')),
            ),
          ],
        ),
      ),
      data: (alerts) {
        if (alerts.isEmpty) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.notifications_none,
                    size: 64, color: cs.onSurfaceVariant),
                const SizedBox(height: 12),
                Text(
                  context.s('no_alerts'),
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: cs.onSurface,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  context.s('no_alerts_hint'),
                  textAlign: TextAlign.center,
                  style: TextStyle(color: cs.onSurfaceVariant),
                ),
              ],
            ),
          );
        }
        return RefreshIndicator(
          onRefresh: () async => ref.invalidate(userAlertsProvider),
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: alerts.length,
            separatorBuilder: (_, __) =>
                const Divider(height: 1, indent: 72),
            itemBuilder: (_, i) => _AlertTile(
              alert: alerts[i],
              onDelete: () async {
                final uid =
                    ref.read(authStateProvider).valueOrNull?.uid ?? '';
                await ref
                    .read(apiServiceProvider)
                    .deleteAlert(alerts[i]['alert_id'] as String, uid);
                ref.invalidate(userAlertsProvider);
              },
            ),
          ),
        );
      },
    );
  }
}

class _AlertTile extends StatelessWidget {
  const _AlertTile({required this.alert, required this.onDelete});

  final Map<String, dynamic> alert;
  final VoidCallback onDelete;

  Future<bool> _confirmDelete(BuildContext context) async {
    return await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: Text(context.s('remove_alert')),
            content: Text(context.s('remove_alert_body')),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: Text(context.s('cancel')),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: Text(context.s('remove')),
              ),
            ],
          ),
        ) ??
        false;
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final productId = alert['product_id'] as String? ?? '';
    // Prefer human-readable title; fall back to product_id
    final title = alert['title'] as String? ??
        alert['product_title'] as String? ??
        productId;
    final marketplace = alert['marketplace_country'] as String? ?? '';
    final targetPrice = alert['target_price'];
    final thresholdPct = alert['alert_threshold_pct'];
    final lastAlerted = alert['last_alerted_at'];
    final createdAt = alert['created_at'] as String?;

    String subtitle;
    if (targetPrice != null) {
      subtitle = '${context.s('alert_target')} ${_fmtPrice(targetPrice, marketplace)}';
    } else if (thresholdPct != null) {
      subtitle =
          '${context.s('alert_pct')} ${thresholdPct.toStringAsFixed(0)}${context.s('alert_pct_suffix')}';
    } else {
      subtitle = context.s('any_price_drop');
    }

    String? dateStr;
    if (createdAt != null) {
      try {
        final dt = DateTime.parse(createdAt);
        dateStr = DateFormat('d MMM y').format(dt);
      } catch (_) {}
    }

    return Dismissible(
      key: Key(alert['alert_id'] as String? ?? productId),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        color: cs.errorContainer,
        child: Icon(Icons.notifications_off_outlined,
            color: cs.onErrorContainer),
      ),
      confirmDismiss: (_) => _confirmDelete(context),
      onDismissed: (_) => onDelete(),
      child: ListTile(
        onTap: () => context.go('/home/deal/$productId'),
        leading: CircleAvatar(
          backgroundColor: cs.primaryContainer,
          child: Icon(Icons.notifications_active_outlined,
              color: cs.onPrimaryContainer, size: 20),
        ),
        title: Text(
          title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w500),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(subtitle,
                style: TextStyle(color: cs.primary, fontSize: 13)),
            if (lastAlerted != null)
              Text(
                '${context.s('last_triggered')} ${_fmtDate(lastAlerted.toString())}',
                style:
                    TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
              )
            else if (dateStr != null)
              Text(
                '${context.s('set_on')} $dateStr',
                style:
                    TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
              ),
          ],
        ),
        trailing: IconButton(
          icon: Icon(Icons.delete_outline, color: cs.error),
          tooltip: 'Remove alert',
          onPressed: () async {
            if (await _confirmDelete(context)) onDelete();
          },
        ),
        isThreeLine: true,
      ),
    );
  }

  String _fmtPrice(dynamic price, String marketplace) {
    final currency = marketplace.contains('_ae') ||
            marketplace.contains('_sa') ||
            marketplace.contains('_kw')
        ? 'AED'
        : 'EGP';
    final n = NumberFormat('#,##0.##');
    return '${n.format(price)} $currency';
  }

  String _fmtDate(String iso) {
    try {
      return DateFormat('d MMM y').format(DateTime.parse(iso));
    } catch (_) {
      return iso;
    }
  }
}
