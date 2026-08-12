import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

import '../providers/auth_provider.dart';
import '../providers/locale_provider.dart';
import '../routes/app_router.dart';
import '../theme/app_colors.dart';
import '../widgets/common_widgets.dart';

/// SCR-003 Registration — same visual language as Login.
class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(authProvider.notifier).clearError();
    });
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);

    final success = await ref.read(authProvider.notifier).register(
          fullName: _nameController.text.trim(),
          email: _emailController.text.trim(),
          phone: _phoneController.text.trim(),
          password: _passwordController.text,
        );

    if (!mounted) return;
    setState(() => _submitting = false);

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Account created. Please log in.')),
      );
      context.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final s = ref.watch(appStringsProvider);

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    InkWell(
                      onTap: () => context.canPop() ? context.pop() : context.go(AppRoutes.login),
                      borderRadius: BorderRadius.circular(12),
                      child: Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: AppColors.surfaceMuted,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppColors.borderLight),
                        ),
                        child: const Icon(Icons.chevron_left, color: AppColors.textPrimary),
                      ),
                    ),
                    const Spacer(),
                    Text(s.t('createAccount'), style: GoogleFonts.poppins(fontSize: 18, fontWeight: FontWeight.w700)),
                    const Spacer(),
                    const SizedBox(width: 44),
                  ],
                ),
                const SizedBox(height: 28),
                Text('${s.t('joinTitle')} 🌱', style: GoogleFonts.poppins(fontSize: 26, fontWeight: FontWeight.w800, color: AppColors.textPrimary)),
                const SizedBox(height: 6),
                Text(
                  s.t('joinSubtitle'),
                  style: GoogleFonts.poppins(color: AppColors.textSecondary, fontSize: 13),
                ),
                const SizedBox(height: 24),
                Text(s.t('fullName'), style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _nameController,
                  decoration: const InputDecoration(hintText: 'Pavan Reddy'),
                  validator: (v) => (v == null || v.trim().length < 2) ? 'Enter your full name' : null,
                ),
                const SizedBox(height: 18),
                Text(s.t('email'), style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _emailController,
                  decoration: const InputDecoration(hintText: 'you@example.com'),
                  keyboardType: TextInputType.emailAddress,
                  validator: (v) => (v == null || !v.contains('@')) ? 'Enter a valid email address' : null,
                ),
                const SizedBox(height: 18),
                Text(s.t('phoneNumber'), style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _phoneController,
                  decoration: const InputDecoration(hintText: '+91 98765 43210'),
                  keyboardType: TextInputType.phone,
                  validator: (v) {
                    if (v == null) return 'Enter your phone number';
                    final digitsOnly = v.replaceAll(RegExp(r'[^0-9]'), '');
                    if (digitsOnly.length < 10 || digitsOnly.length > 15) {
                      return 'Phone must be 10-15 digits';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 18),
                Text(s.t('password'), style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _passwordController,
                  obscureText: _obscurePassword,
                  decoration: InputDecoration(
                    helperText: s.t('passwordHelper'),
                    suffixIcon: IconButton(
                      icon: Icon(_obscurePassword ? Icons.visibility_off_outlined : Icons.visibility_outlined),
                      onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                    ),
                  ),
                  validator: (v) {
                    if (v == null || v.length < 8) return 'Minimum 8 characters';
                    if (!RegExp(r'[A-Za-z]').hasMatch(v) || !RegExp(r'[0-9]').hasMatch(v)) {
                      return 'Must contain a letter and a number';
                    }
                    return null;
                  },
                ),
                if (authState is AuthError) ...[
                  const SizedBox(height: 8),
                  Text(authState.message, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 24),
                PrimaryButton(label: s.t('createAccount'), onPressed: _submit, isLoading: _submitting),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
