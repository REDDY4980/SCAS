import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';

import '../providers/locale_provider.dart';
import '../providers/repository_providers.dart';
import '../routes/app_router.dart';
import '../services/api_exception.dart';
import '../theme/app_colors.dart';
import '../widgets/common_widgets.dart';

/// SCR-006 Upload Soil Report — matches reference design: dashed-border
/// drop zone, "Upload Options" button, then a grid of 3 real source
/// options (PDF / Gallery / Camera). Backed by the real, tested
/// POST /soil/upload endpoint (Phase 4).
class UploadScreen extends ConsumerStatefulWidget {
  final String farmId;
  const UploadScreen({super.key, required this.farmId});

  @override
  ConsumerState<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends ConsumerState<UploadScreen> {
  bool _uploading = false;
  String? _error;

  static const _allowedExtensions = ['pdf', 'jpg', 'jpeg', 'png'];
  static const _maxSizeMb = 10; // Vol 7.2

  Future<void> _pickFromCamera() async {
    final picker = ImagePicker();
    final photo = await picker.pickImage(source: ImageSource.camera, imageQuality: 90);
    if (photo == null) return;
    await _handlePickedFile(await photo.readAsBytes(), photo.name);
  }

  Future<void> _pickFromGallery() async {
    final picker = ImagePicker();
    final photo = await picker.pickImage(source: ImageSource.gallery, imageQuality: 90);
    if (photo == null) return;
    await _handlePickedFile(await photo.readAsBytes(), photo.name);
  }

  Future<void> _pickPdf() async {
    // withData forces file_picker to load bytes on every platform (on
    // web only `bytes` is ever populated — `path` is always null there
    // since there's no filesystem to point to).
    final result = await FilePicker.platform
        .pickFiles(type: FileType.custom, allowedExtensions: ['pdf'], withData: true);
    final picked = result?.files.single;
    final bytes = picked?.bytes;
    final name = picked?.name;
    if (bytes != null && name != null) await _handlePickedFile(bytes, name);
  }

  Future<void> _handlePickedFile(Uint8List bytes, String fileName) async {
    final extension = fileName.split('.').last.toLowerCase();
    if (!_allowedExtensions.contains(extension)) {
      setState(() => _error = 'Unsupported file type. Please use PDF, JPG, or PNG.');
      return;
    }
    if (bytes.lengthInBytes > _maxSizeMb * 1024 * 1024) {
      setState(() => _error = 'File exceeds the ${_maxSizeMb}MB upload limit.');
      return;
    }

    setState(() {
      _uploading = true;
      _error = null;
    });

    try {
      final soilRepo = ref.read(soilRepositoryProvider);
      final result = await soilRepo.uploadReport(farmId: widget.farmId, bytes: bytes, fileName: fileName);
      if (!mounted) return;
      context.push('${AppRoutes.aiAnalysis}?farmId=${widget.farmId}&reportId=${result.reportId}');
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = 'Something went wrong while uploading. Please try again.');
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(appStringsProvider);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  InkWell(
                    onTap: () => context.canPop() ? context.pop() : context.go(AppRoutes.dashboard),
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
                  Text(s.t('soilAnalysisOcr'), style: GoogleFonts.poppins(fontSize: 18, fontWeight: FontWeight.w700)),
                  const Spacer(),
                  const SizedBox(width: 44),
                ],
              ),
              const SizedBox(height: 24),
              if (_uploading)
                const Expanded(child: LoadingView(message: 'Uploading your report...'))
              else
                Expanded(
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(vertical: 36, horizontal: 20),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(AppRadii.card),
                            border: Border.all(color: AppColors.borderDashed, width: 1.5, style: BorderStyle.solid),
                          ),
                          child: Column(
                            children: [
                              Container(
                                width: 56,
                                height: 56,
                                decoration: BoxDecoration(color: AppColors.surfaceMuted, shape: BoxShape.circle),
                                child: const Icon(Icons.upload_outlined, color: AppColors.primary, size: 26),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                s.t('tapOrDrag'),
                                style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 15),
                              ),
                              const SizedBox(height: 20),
                              PrimaryButton(label: s.t('uploadOptions'), icon: Icons.upload_outlined, onPressed: _pickFromGallery),
                            ],
                          ),
                        ),
                        const SizedBox(height: 28),
                        Text(s.t('uploadOptions'), style: GoogleFonts.poppins(fontSize: 15, fontWeight: FontWeight.w800)),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(child: _SourceCard(icon: Icons.description_outlined, label: s.t('pdfDocument'), onTap: _pickPdf)),
                            const SizedBox(width: 12),
                            Expanded(child: _SourceCard(icon: Icons.image_outlined, label: s.t('photoGallery'), onTap: _pickFromGallery)),
                            const SizedBox(width: 12),
                            Expanded(child: _SourceCard(icon: Icons.camera_alt_outlined, label: s.t('cameraCapture'), onTap: _pickFromCamera)),
                          ],
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 16),
                          Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                        ],
                        const SizedBox(height: 8),
                        Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Text(
                            'Max ${_maxSizeMb}MB. PDF, JPG, or PNG.',
                            style: GoogleFonts.poppins(fontSize: 12, color: AppColors.textSecondary),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SourceCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _SourceCard({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 18),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.borderLight),
        ),
        child: Column(
          children: [
            Icon(icon, color: AppColors.primary, size: 26),
            const SizedBox(height: 8),
            Text(
              label,
              textAlign: TextAlign.center,
              style: GoogleFonts.poppins(fontSize: 12, fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
    );
  }
}
