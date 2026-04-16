// lib/screens/deals/deals_list_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../providers/deals_provider.dart';
import '../../services/permission_service.dart';

class DealsListScreen extends ConsumerStatefulWidget {
  const DealsListScreen({Key? key}) : super(key: key);

  @override
  ConsumerState<DealsListScreen> createState() => _DealsListScreenState();
}

class _DealsListScreenState extends ConsumerState<DealsListScreen> {
  String _searchQuery = '';
  String _selectedSource = 'all';
  String _selectedStatus = 'all';
  bool _showFeaturedOnly = false;

  @override
  Widget build(BuildContext context) {
    final permissionService = ref.read(permissionServiceProvider);
    final dealsAsync = ref.watch(dealsProvider);

    // Check permission
    if (!permissionService.canAccessPage('deals', {})) {
      return Scaffold(
        appBar: AppBar(title: const Text('Deals Management')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.lock, size: 64, color: Colors.red.shade300),
              const SizedBox(height: 16),
              Text(
                'Access Denied',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                'You do not have permission to manage deals',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Deals Management'),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.refresh(dealsProvider),
            tooltip: 'Refresh deals list',
          ),
        ],
      ),
      body: dealsAsync.when(
        data: (deals) {
          // Filter deals
          final filtered = deals.where((deal) {
            final matchesSearch = deal.title
                    .toLowerCase()
                    .contains(_searchQuery.toLowerCase()) ||
                deal.site.toLowerCase().contains(_searchQuery.toLowerCase());

            final matchesSource = _selectedSource == 'all' ||
                deal.site.toLowerCase() == _selectedSource.toLowerCase();

            final matchesStatus =
                _selectedStatus == 'all' || deal.status == _selectedStatus;

            final matchesFeatured = !_showFeaturedOnly || deal.isFeatured;

            return matchesSearch &&
                matchesSource &&
                matchesStatus &&
                matchesFeatured;
          }).toList();

          return Column(
            children: [
              // Search & Filter Section
              Container(
                padding: const EdgeInsets.all(16),
                color: Colors.grey.shade50,
                child: Column(
                  children: [
                    // Search field
                    TextField(
                      decoration: InputDecoration(
                        labelText: 'Search deals by title or source',
                        hintText: 'iPhone, Amazon, Jumia...',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                        prefixIcon: const Icon(Icons.search),
                        suffixIcon: _searchQuery.isNotEmpty
                            ? IconButton(
                                icon: const Icon(Icons.clear),
                                onPressed: () =>
                                    setState(() => _searchQuery = ''),
                              )
                            : null,
                      ),
                      onChanged: (value) =>
                          setState(() => _searchQuery = value),
                    ),
                    const SizedBox(height: 16),

                    // Source Filter
                    Row(
                      children: [
                        const Text('Source: '),
                        const SizedBox(width: 8),
                        Expanded(
                          child: SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: Row(
                              children: ['all', 'amazon', 'jumia', 'noon']
                                  .map((source) {
                                return Padding(
                                  padding:
                                      const EdgeInsets.symmetric(horizontal: 4),
                                  child: FilterChip(
                                    label: Text(source.toUpperCase()),
                                    selected: _selectedSource == source,
                                    onSelected: (selected) {
                                      setState(
                                        () => _selectedSource =
                                            selected ? source : 'all',
                                      );
                                    },
                                  ),
                                );
                              }).toList(),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Status Filter
                    Row(
                      children: [
                        const Text('Status: '),
                        const SizedBox(width: 8),
                        Expanded(
                          child: SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: Row(
                              children: ['all', 'active', 'hidden', 'expired']
                                  .map((status) {
                                return Padding(
                                  padding:
                                      const EdgeInsets.symmetric(horizontal: 4),
                                  child: FilterChip(
                                    label: Text(status.toUpperCase()),
                                    selected: _selectedStatus == status,
                                    onSelected: (selected) {
                                      setState(
                                        () => _selectedStatus =
                                            selected ? status : 'all',
                                      );
                                    },
                                  ),
                                );
                              }).toList(),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Featured & count
                    Row(
                      children: [
                        Checkbox(
                          value: _showFeaturedOnly,
                          onChanged: (value) =>
                              setState(() => _showFeaturedOnly = value ?? false),
                        ),
                        const Text('Featured Only'),
                        const Spacer(),
                        Text(
                          'Showing ${filtered.length} of ${deals.length}',
                          style: TextStyle(
                            color: Colors.grey.shade600,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              // Deals Table
              Expanded(
                child: filtered.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.local_offer,
                                size: 64, color: Colors.grey.shade300),
                            const SizedBox(height: 16),
                            Text(
                              'No deals found',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(color: Colors.grey),
                            ),
                          ],
                        ),
                      )
                    : SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: DataTable(
                          columnSpacing: 16,
                          dataRowMinHeight: 60,
                          dataRowMaxHeight: 70,
                          columns: [
                            const DataColumn(label: Text('Image')),
                            const DataColumn(label: Text('Title')),
                            const DataColumn(label: Text('Source')),
                            const DataColumn(label: Text('Price')),
                            const DataColumn(label: Text('Discount')),
                            const DataColumn(label: Text('Status')),
                            const DataColumn(label: Text('Verdict')),
                            const DataColumn(label: Text('Featured')),
                            const DataColumn(label: Text('Added')),
                            const DataColumn(label: Text('Actions')),
                          ],
                          rows: filtered.map((deal) {
                            return DataRow(
                              cells: [
                                // Image
                                DataCell(
                                  deal.imageUrl.isNotEmpty
                                      ? Container(
                                          width: 40,
                                          height: 40,
                                          decoration: BoxDecoration(
                                            borderRadius:
                                                BorderRadius.circular(4),
                                            image: DecorationImage(
                                              image: NetworkImage(deal.imageUrl),
                                              fit: BoxFit.cover,
                                            ),
                                          ),
                                        )
                                      : Container(
                                          width: 40,
                                          height: 40,
                                          decoration: BoxDecoration(
                                            borderRadius:
                                                BorderRadius.circular(4),
                                            color: Colors.grey.shade200,
                                          ),
                                          child: Icon(
                                            Icons.image_not_supported,
                                            size: 20,
                                            color: Colors.grey.shade400,
                                          ),
                                        ),
                                ),

                                // Title
                                DataCell(
                                  SizedBox(
                                    width: 150,
                                    child: Text(
                                      deal.title,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ),

                                // Source
                                DataCell(
                                  Chip(
                                    label: Text(deal.site),
                                    backgroundColor: Colors.blue.shade100,
                                    labelStyle: TextStyle(
                                      color: Colors.blue.shade700,
                                      fontSize: 10,
                                    ),
                                  ),
                                ),

                                // Price
                                DataCell(
                                  Text(
                                    'EGP ${deal.currentPrice.toStringAsFixed(0)}',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),

                                // Discount
                                DataCell(
                                  Chip(
                                    label: Text('${deal.discountPercent}%'),
                                    backgroundColor: Colors.red.shade100,
                                    labelStyle: TextStyle(
                                      color: Colors.red.shade700,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 11,
                                    ),
                                  ),
                                ),

                                // Status
                                DataCell(
                                  Chip(
                                    label: Text(deal.status.toUpperCase()),
                                    backgroundColor: _getStatusColor(deal.status)
                                        .withOpacity(0.2),
                                    labelStyle: TextStyle(
                                      color: _getStatusColor(deal.status),
                                      fontSize: 10,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),

                                // Verdict
                                DataCell(
                                  Tooltip(
                                    message: deal.fakeVerdict.toUpperCase(),
                                    child: Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 4,
                                      ),
                                      decoration: BoxDecoration(
                                        color: _getVerdictColor(deal.fakeVerdict)
                                            .withOpacity(0.2),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Icon(
                                            _getVerdictIcon(deal.fakeVerdict),
                                            size: 14,
                                            color: _getVerdictColor(
                                                deal.fakeVerdict),
                                          ),
                                          const SizedBox(width: 4),
                                          Text(
                                            deal.fakeVerdict[0].toUpperCase(),
                                            style: TextStyle(
                                              color: _getVerdictColor(
                                                  deal.fakeVerdict),
                                              fontSize: 10,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),

                                // Featured
                                DataCell(
                                  Icon(
                                    deal.isFeatured
                                        ? Icons.star
                                        : Icons.star_border,
                                    color: deal.isFeatured
                                        ? Colors.orange
                                        : Colors.grey,
                                  ),
                                ),

                                // Added
                                DataCell(
                                  Text(
                                    _formatDate(deal.addedAt),
                                    style: const TextStyle(fontSize: 11),
                                  ),
                                ),

                                // Actions
                                DataCell(
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      IconButton(
                                        icon: const Icon(Icons.edit, size: 18),
                                        tooltip: 'Edit deal',
                                        onPressed: () =>
                                            _showEditDialog(context, deal),
                                      ),
                                      IconButton(
                                        icon: const Icon(Icons.visibility_off,
                                            size: 18),
                                        tooltip: deal.status == 'active'
                                            ? 'Hide deal'
                                            : 'Show deal',
                                        onPressed: () =>
                                            _toggleVisibility(context, deal),
                                      ),
                                      IconButton(
                                        icon: const Icon(Icons.star,
                                            size: 18, color: Colors.orange),
                                        tooltip: deal.isFeatured
                                            ? 'Unfeature deal'
                                            : 'Feature deal',
                                        onPressed: () =>
                                            _toggleFeatured(context, deal),
                                      ),
                                      IconButton(
                                        icon: const Icon(Icons.delete,
                                            size: 18, color: Colors.red),
                                        tooltip: 'Delete deal',
                                        onPressed: () =>
                                            _showDeleteDialog(context, deal),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            );
                          }).toList(),
                        ),
                      ),
              ),
            ],
          );
        },
        loading: () => Scaffold(
          appBar: AppBar(title: const Text('Deals Management')),
          body: const Center(child: CircularProgressIndicator()),
        ),
        error: (error, stack) => Scaffold(
          appBar: AppBar(title: const Text('Deals Management')),
          body: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.error, size: 64, color: Colors.red.shade300),
                const SizedBox(height: 16),
                Text(
                  'Error loading deals',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                Text(
                  error.toString(),
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.red.shade600),
                ),
                const SizedBox(height: 24),
                ElevatedButton.icon(
                  onPressed: () => ref.refresh(dealsProvider),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showEditDialog(BuildContext context, DealModel deal) {
    final titleController = TextEditingController(text: deal.title);
    final currentPriceController =
        TextEditingController(text: deal.currentPrice.toString());
    final originalPriceController =
        TextEditingController(text: deal.originalPrice.toString());
    String selectedVerdict = deal.fakeVerdict;
    bool isFeatured = deal.isFeatured;
    bool isLoading = false;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: const Text('Edit Deal'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Title
                TextFormField(
                  controller: titleController,
                  decoration: InputDecoration(
                    labelText: 'Deal Title',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Prices
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: currentPriceController,
                        decoration: InputDecoration(
                          labelText: 'Current Price',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                        keyboardType: TextInputType.number,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextFormField(
                        controller: originalPriceController,
                        decoration: InputDecoration(
                          labelText: 'Original Price',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                        keyboardType: TextInputType.number,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Fake Verdict
                DropdownButtonFormField<String>(
                  value: selectedVerdict,
                  decoration: InputDecoration(
                    labelText: 'Fraud Verdict',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  items: ['genuine', 'suspicious', 'fake']
                      .map((verdict) => DropdownMenuItem(
                            value: verdict,
                            child: Text(verdict.toUpperCase()),
                          ))
                      .toList(),
                  onChanged: (value) {
                    if (value != null) {
                      setState(() => selectedVerdict = value);
                    }
                  },
                ),
                const SizedBox(height: 16),

                // Featured toggle
                SwitchListTile(
                  title: const Text('Featured'),
                  subtitle: Text(
                    isFeatured
                        ? 'Deal appears at top of list'
                        : 'Regular listing',
                  ),
                  value: isFeatured,
                  onChanged: (value) => setState(() => isFeatured = value),
                  contentPadding: EdgeInsets.zero,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: isLoading ? null : () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: isLoading
                  ? null
                  : () async {
                      setState(() => isLoading = true);

                      try {
                        final updates = {
                          'title': titleController.text.trim(),
                          'current_price':
                              double.parse(currentPriceController.text),
                          'original_price':
                              double.parse(originalPriceController.text),
                          'fake_verdict': selectedVerdict,
                          'featured': isFeatured,
                        };

                        await ref.read(updateDealProvider(
                          (deal.id, updates),
                        ).future);

                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Deal updated successfully'),
                              backgroundColor: Colors.green,
                            ),
                          );
                          Navigator.pop(context);
                        }
                      } catch (e) {
                        setState(() => isLoading = false);
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('Error: $e'),
                              backgroundColor: Colors.red,
                            ),
                          );
                        }
                      }
                    },
              child: isLoading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  void _toggleVisibility(BuildContext context, DealModel deal) async {
    try {
      final newStatus = deal.status == 'active' ? 'hidden' : 'active';
      await ref.read(updateDealProvider(
        (deal.id, {'status': newStatus}),
      ).future);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              newStatus == 'active' ? 'Deal shown' : 'Deal hidden',
            ),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _toggleFeatured(BuildContext context, DealModel deal) async {
    try {
      await ref.read(updateDealProvider(
        (deal.id, {'featured': !deal.isFeatured}),
      ).future);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              deal.isFeatured ? 'Deal unpinned' : 'Deal pinned to top',
            ),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _showDeleteDialog(BuildContext context, DealModel deal) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Deal?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Are you sure you want to delete this deal?'),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    deal.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'EGP ${deal.currentPrice.toStringAsFixed(0)}',
                    style: const TextStyle(fontFamily: 'monospace'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'This action cannot be undone.',
              style: TextStyle(fontWeight: FontWeight.bold, color: Colors.red),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              try {
                await ref.read(deleteDealProvider(deal.id).future);
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Deal deleted successfully'),
                      backgroundColor: Colors.green,
                    ),
                  );
                  Navigator.pop(context);
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Error: $e'),
                      backgroundColor: Colors.red,
                    ),
                  );
                }
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) {
    return DateFormat('MMM d, yyyy').format(date);
  }

  Color _getStatusColor(String status) {
    return {
      'active': Colors.green,
      'hidden': Colors.orange,
      'expired': Colors.red,
    }[status] ??
        Colors.grey;
  }

  Color _getVerdictColor(String verdict) {
    return {
      'genuine': Colors.green,
      'suspicious': Colors.orange,
      'fake': Colors.red,
    }[verdict] ??
        Colors.grey;
  }

  IconData _getVerdictIcon(String verdict) {
    return {
      'genuine': Icons.check_circle,
      'suspicious': Icons.warning,
      'fake': Icons.cancel,
    }[verdict] ??
        Icons.help;
  }
}
