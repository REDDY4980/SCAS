import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

import '../localization/app_strings.dart';
import '../providers/auth_provider.dart';
import '../providers/locale_provider.dart';
import '../routes/app_router.dart';
import '../theme/app_colors.dart';
import '../widgets/common_widgets.dart';

/// SCR-002 Login Screen — matches reference design, with a REAL working
/// language switcher (AppLanguage -> localeProvider) rather than a
/// cosmetic-only toggle.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _identifierController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(authProvider.notifier).clearError();
    });
  }

  @override
  void dispose() {
    _identifierController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    ref.read(authProvider.notifier).login(
          identifier: _identifierController.text.trim(),
          password: _passwordController.text,
        );
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final isLoading = authState is AuthLoading;
    final s = ref.watch(appStringsProvider);
    final currentLanguage = ref.watch(localeProvider);

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
                    _BackButton(onTap: () => context.canPop() ? context.pop() : context.go(AppRoutes.splash)),
                    const Spacer(),
                    Text(s.t('login'), style: GoogleFonts.poppins(fontSize: 18, fontWeight: FontWeight.w700)),
                    const Spacer(),
                    const SizedBox(width: 44),
                  ],
                ),
                const SizedBox(height: 28),
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(
                        text: '${s.t('welcomeBack')} ',
                        style: GoogleFonts.poppins(fontSize: 26, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                      ),
                      const TextSpan(text: '👋', style: TextStyle(fontSize: 22)),
                    ],
                  ),
                ),
                const SizedBox(height: 6),
                Text(s.t('loginSubtitle'), style: GoogleFonts.poppins(color: AppColors.textSecondary, fontSize: 13)),
                const SizedBox(height: 20),
                // Real, working language switcher — persists locally
                // immediately and syncs to the backend profile once
                // logged in (see LocaleNotifier.setLanguage).
                Wrap(
                  spacing: 8,
                  children: AppLanguage.values
                      .map((lang) => LanguageChip(
                            label: lang.nativeName,
                            selected: currentLanguage == lang,
                            onTap: () => ref.read(localeProvider.notifier).setLanguage(lang, ref: ref),
                          ))
                      .toList(),
                ),
                const SizedBox(height: 24),
                Text(s.t('emailOrMobile'), style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _identifierController,
                  decoration: const InputDecoration(hintText: '+91 98765 43210'),
                  keyboardType: TextInputType.emailAddress,
                  validator: (v) => (v == null || v.trim().length < 3) ? 'Enter your email or phone' : null,
                ),
                const SizedBox(height: 18),
                Text(s.t('password'), style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _passwordController,
                  obscureText: _obscurePassword,
                  decoration: InputDecoration(
                    suffixIcon: IconButton(
                      icon: Icon(_obscurePassword ? Icons.visibility_off_outlined : Icons.visibility_outlined),
                      onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                    ),
                  ),
                  validator: (v) => (v == null || v.isEmpty) ? 'Enter your password' : null,
                  onFieldSubmitted: (_) => _submit(),
                ),
                const SizedBox(height: 10),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () {},
                    child: Text(s.t('forgotPassword'), style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 13)),
                  ),
                ),
                if (authState is AuthError) ...[
                  const SizedBox(height: 8),
                  Text(authState.message, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 12),
                PrimaryButton(label: s.t('login'), onPressed: _submit, isLoading: isLoading),
                const SizedBox(height: 20),
                Center(
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text('${s.t('createAccount')} ', style: GoogleFonts.poppins(color: AppColors.textSecondary, fontSize: 13)),
                      InkWell(
                        onTap: () => context.push(AppRoutes.register),
                        child: Text(
                          s.t('signUp'),
                          style: GoogleFonts.poppins(color: AppColors.primary, fontWeight: FontWeight.w700, fontSize: 13),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _BackButton extends StatelessWidget {
  final VoidCallback onTap;
  const _BackButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
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
    );
  }
}
