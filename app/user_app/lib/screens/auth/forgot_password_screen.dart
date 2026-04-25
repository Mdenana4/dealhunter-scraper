import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../config/theme.dart';

class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  ConsumerState<ForgotPasswordScreen> createState() =>
      _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> {
  final _formKey  = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  bool _isLoading = false;
  bool _sent = false;

  @override
  void dispose() {
    _emailCtrl.dispose();
    super.dispose();
  }

  Future<void> _sendReset() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);
    final ok = await ref.read(authNotifierProvider.notifier)
        .sendPasswordReset(_emailCtrl.text.trim());
    if (!mounted) return;
    setState(() {
      _isLoading = false;
      _sent = ok;
    });
    if (!ok) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Could not send reset email. Check the address and try again.'),
        backgroundColor: AppTheme.fake,
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Reset Password'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new),
          onPressed: () => context.pop(),
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
          child: _sent ? _successView() : _formView(),
        ),
      ),
    );
  }

  Widget _formView() => Form(
    key: _formKey,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Icon(Icons.lock_reset, size: 72, color: AppTheme.primary),
        const SizedBox(height: 24),
        Text('Forgot your password?',
            style: Theme.of(context).textTheme.headlineMedium,
            textAlign: TextAlign.center),
        const SizedBox(height: 12),
        Text(
          'Enter your email address and we\'ll send you a link to reset your password.',
          style: Theme.of(context).textTheme.bodyMedium
              ?.copyWith(color: Colors.grey),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 36),
        TextFormField(
          controller: _emailCtrl,
          keyboardType: TextInputType.emailAddress,
          textInputAction: TextInputAction.done,
          onFieldSubmitted: (_) => _sendReset(),
          decoration: const InputDecoration(
            labelText: 'Email address',
            prefixIcon: Icon(Icons.email_outlined),
          ),
          validator: (v) {
            if (v == null || v.isEmpty) return 'Email is required';
            if (!v.contains('@')) return 'Enter a valid email';
            return null;
          },
        ),
        const SizedBox(height: 24),
        ElevatedButton(
          onPressed: _isLoading ? null : _sendReset,
          child: _isLoading
              ? const SizedBox(
                  height: 22, width: 22,
                  child: CircularProgressIndicator(
                      color: Colors.white, strokeWidth: 2))
              : const Text('Send Reset Link'),
        ),
      ],
    ),
  );

  Widget _successView() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const Icon(Icons.mark_email_read_rounded,
          size: 80, color: AppTheme.genuine),
      const SizedBox(height: 24),
      Text('Check your inbox!',
          style: Theme.of(context).textTheme.headlineMedium,
          textAlign: TextAlign.center),
      const SizedBox(height: 12),
      Text(
        'We\'ve sent a password reset link to\n${_emailCtrl.text.trim()}',
        style: Theme.of(context).textTheme.bodyMedium
            ?.copyWith(color: Colors.grey),
        textAlign: TextAlign.center,
      ),
      const SizedBox(height: 8),
      Text(
        'Check your spam folder if you don\'t see it within a few minutes.',
        style: Theme.of(context).textTheme.bodySmall
            ?.copyWith(color: Colors.grey),
        textAlign: TextAlign.center,
      ),
      const SizedBox(height: 36),
      ElevatedButton(
        onPressed: () => context.go('/login'),
        child: const Text('Back to Sign In'),
      ),
      const SizedBox(height: 12),
      TextButton(
        onPressed: () => setState(() => _sent = false),
        child: const Text('Resend email'),
      ),
    ],
  );
}
