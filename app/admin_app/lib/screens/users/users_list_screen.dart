// lib/screens/users/users_list_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../providers/users_provider.dart';
import '../../services/permission_service.dart';
import '../../models/user.dart';

class UsersListScreen extends ConsumerStatefulWidget {
  const UsersListScreen({Key? key}) : super(key: key);

  @override
  ConsumerState<UsersListScreen> createState() => _UsersListScreenState();
}

class _UsersListScreenState extends ConsumerState<UsersListScreen> {
  String _searchQuery = '';
  String _selectedTier = 'all';
  bool _showOnlyActive = true;

  @override
  Widget build(BuildContext context) {
    final permissionService = ref.read(permissionServiceProvider);
    final usersAsync = ref.watch(usersProvider);

    // Check permission
    if (!permissionService.canAccessPage('users', {})) {
      return Scaffold(
        appBar: AppBar(title: const Text('Users Management')),
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
                'You do not have permission to access Users Management',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Users Management'),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.refresh(usersProvider),
            tooltip: 'Refresh users list',
          ),
        ],
      ),
      body: usersAsync.when(
        data: (users) {
          // Filter users
          final filtered = users.where((user) {
            final matchesSearch =
                user.email.toLowerCase().contains(_searchQuery.toLowerCase()) ||
                (user.name?.toLowerCase().contains(_searchQuery.toLowerCase()) ??
                    false);

            final matchesTier =
                _selectedTier == 'all' || user.tier == _selectedTier;

            final matchesActive = !_showOnlyActive || user.isActive;

            return matchesSearch && matchesTier && matchesActive;
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
                        labelText: 'Search users by email or name',
                        hintText: 'admin@example.com',
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

                    // Filters
                    Row(
                      children: [
                        Expanded(
                          child: SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: Row(
                              children: ['all', 'free', 'trial', 'premium', 'vip']
                                  .map((tier) {
                                return Padding(
                                  padding:
                                      const EdgeInsets.symmetric(horizontal: 4),
                                  child: FilterChip(
                                    label: Text(tier.toUpperCase()),
                                    selected: _selectedTier == tier,
                                    onSelected: (selected) {
                                      setState(
                                        () => _selectedTier =
                                            selected ? tier : 'all',
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

                    // Active/Inactive toggle
                    Row(
                      children: [
                        Switch(
                          value: _showOnlyActive,
                          onChanged: (value) =>
                              setState(() => _showOnlyActive = value),
                        ),
                        const Text('Active Users Only'),
                        const Spacer(),
                        Text(
                          'Showing ${filtered.length} of ${users.length}',
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

              // Users Table
              Expanded(
                child: filtered.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.person_off,
                                size: 64, color: Colors.grey.shade300),
                            const SizedBox(height: 16),
                            Text(
                              'No users found',
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
                          dataRowMinHeight: 50,
                          dataRowMaxHeight: 60,
                          columns: [
                            DataColumn(
                              label: const Text('Email'),
                              onSort: (columnIndex, ascending) {},
                            ),
                            DataColumn(
                              label: const Text('Name'),
                              onSort: (columnIndex, ascending) {},
                            ),
                            const DataColumn(label: Text('Tier')),
                            const DataColumn(label: Text('Daily Limit')),
                            const DataColumn(label: Text('Registered')),
                            const DataColumn(label: Text('Last Login')),
                            const DataColumn(label: Text('Status')),
                            const DataColumn(label: Text('Actions')),
                          ],
                          rows: filtered.map((user) {
                            return DataRow(
                              cells: [
                                DataCell(
                                  Text(
                                    user.email,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                DataCell(Text(user.name ?? '—')),
                                DataCell(
                                  Chip(
                                    label: Text(user.tier.toUpperCase()),
                                    backgroundColor:
                                        _getTierColor(user.tier).withOpacity(0.2),
                                    labelStyle: TextStyle(
                                      color: _getTierColor(user.tier),
                                      fontWeight: FontWeight.bold,
                                      fontSize: 11,
                                    ),
                                  ),
                                ),
                                DataCell(Text('${user.dailyDealLimit}')),
                                DataCell(
                                  Text(
                                    _formatDate(user.registeredAt),
                                    style: const TextStyle(fontSize: 12),
                                  ),
                                ),
                                DataCell(
                                  Text(
                                    user.lastLogin != null
                                        ? _formatDate(user.lastLogin!)
                                        : 'Never',
                                    style: const TextStyle(fontSize: 12),
                                  ),
                                ),
                                DataCell(
                                  Chip(
                                    label: Text(user.isActive ? 'Active' : 'Inactive'),
                                    backgroundColor: user.isActive
                                        ? Colors.green.shade100
                                        : Colors.grey.shade200,
                                    labelStyle: TextStyle(
                                      color: user.isActive
                                          ? Colors.green.shade700
                                          : Colors.grey.shade700,
                                      fontSize: 11,
                                    ),
                                  ),
                                ),
                                DataCell(
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      IconButton(
                                        icon: const Icon(Icons.edit, size: 18),
                                        tooltip: 'Edit user',
                                        onPressed: () =>
                                            _showEditDialog(context, user),
                                      ),
                                      IconButton(
                                        icon: const Icon(Icons.delete,
                                            size: 18, color: Colors.red),
                                        tooltip: 'Delete user',
                                        onPressed: () =>
                                            _showDeleteDialog(context, user),
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
          appBar: AppBar(title: const Text('Users Management')),
          body: const Center(child: CircularProgressIndicator()),
        ),
        error: (error, stack) => Scaffold(
          appBar: AppBar(title: const Text('Users Management')),
          body: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.error, size: 64, color: Colors.red.shade300),
                const SizedBox(height: 16),
                Text(
                  'Error loading users',
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
                  onPressed: () => ref.refresh(usersProvider),
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

  void _showEditDialog(BuildContext context, UserModel user) {
    final nameController = TextEditingController(text: user.name ?? '');
    final limitController =
        TextEditingController(text: user.dailyDealLimit.toString());
    String selectedTier = user.tier;
    bool isActive = user.isActive;
    bool isLoading = false;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: const Text('Edit User'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Email (read-only)
                TextFormField(
                  initialValue: user.email,
                  enabled: false,
                  decoration: InputDecoration(
                    labelText: 'Email (read-only)',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Name
                TextFormField(
                  controller: nameController,
                  decoration: InputDecoration(
                    labelText: 'Full Name',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Tier
                DropdownButtonFormField<String>(
                  value: selectedTier,
                  decoration: InputDecoration(
                    labelText: 'Subscription Tier',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  items: ['free', 'trial', 'premium', 'vip']
                      .map((tier) => DropdownMenuItem(
                            value: tier,
                            child: Text(tier.toUpperCase()),
                          ))
                      .toList(),
                  onChanged: (value) {
                    if (value != null) {
                      setState(() => selectedTier = value);
                    }
                  },
                ),
                const SizedBox(height: 16),

                // Daily Deal Limit
                TextFormField(
                  controller: limitController,
                  decoration: InputDecoration(
                    labelText: 'Daily Deal Limit',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 16),

                // Status
                SwitchListTile(
                  title: const Text('Active'),
                  subtitle: Text(isActive ? 'User can login' : 'User is locked'),
                  value: isActive,
                  onChanged: (value) => setState(() => isActive = value),
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
                          'name': nameController.text.trim(),
                          'tier': selectedTier,
                          'daily_deal_limit':
                              int.parse(limitController.text),
                          'is_active': isActive,
                        };

                        // Trigger update
                        await ref
                            .read(updateUserProvider(
                              (user.id, updates),
                            ).future);

                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('User updated successfully'),
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

  void _showDeleteDialog(BuildContext context, UserModel user) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete User?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Are you sure you want to delete this user?'),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '${user.email}\n${user.name ?? "Unknown"}',
                style: const TextStyle(fontFamily: 'monospace'),
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
                await ref.read(deleteUserProvider(user.id).future);
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('User deleted successfully'),
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

  Color _getTierColor(String tier) {
    return {
      'free': Colors.grey,
      'trial': Colors.blue,
      'premium': Colors.green,
      'vip': Colors.purple,
    }[tier] ??
        Colors.grey;
  }
}
