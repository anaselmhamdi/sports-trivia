import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../utils/image_helpers.dart';

/// Validation state for club input
enum ValidationState { idle, validating, valid, invalid }

/// Input field for selecting a club/team
/// Features autocomplete suggestions and real-time validation
class ClubInput extends StatefulWidget {
  final String? label;
  final String? hint;
  final bool enabled;
  final bool autofocus;
  final ValueChanged<String>? onSubmitted;
  final List<ClubInfo> clubs;
  final TextEditingController? controller;
  final String sport;

  const ClubInput({
    super.key,
    this.label,
    this.hint,
    this.enabled = true,
    this.autofocus = false,
    this.onSubmitted,
    this.clubs = const [],
    this.controller,
    this.sport = 'soccer',
  });

  @override
  State<ClubInput> createState() => _ClubInputState();
}

class _ClubInputState extends State<ClubInput> {
  late TextEditingController _controller;
  final FocusNode _focusNode = FocusNode();
  final LayerLink _layerLink = LayerLink();
  OverlayEntry? _overlayEntry;
  List<ClubInfo> _filteredSuggestions = [];
  bool _showSuggestions = false;

  // Validation state
  ValidationState _validationState = ValidationState.idle;
  String? _validationError;
  String? _normalizedName;
  Timer? _debounceTimer;
  final ApiService _apiService = ApiService();

  @override
  void initState() {
    super.initState();
    _controller = widget.controller ?? TextEditingController();
    _controller.addListener(_onTextChanged);
    _focusNode.addListener(_onFocusChanged);
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    if (widget.controller == null) {
      _controller.dispose();
    }
    _focusNode.dispose();
    _removeOverlay();
    super.dispose();
  }

  void _onTextChanged() {
    final query = _controller.text.toLowerCase().trim();

    // Filter suggestions from provided clubs
    if (query.length >= 2 && widget.clubs.isNotEmpty) {
      _filteredSuggestions = widget.clubs
          .where((club) => club.searchTerms.any((term) => term.contains(query)))
          .take(5)
          .toList();
      _showSuggestions = _filteredSuggestions.isNotEmpty;
    } else {
      _filteredSuggestions = [];
      _showSuggestions = false;
    }
    _updateOverlay();

    // Reset validation state when text changes
    if (_validationState != ValidationState.idle) {
      setState(() {
        _validationState = ValidationState.idle;
        _validationError = null;
        _normalizedName = null;
      });
    }

    // Debounce validation
    _debounceTimer?.cancel();
    if (query.length >= 2) {
      _debounceTimer = Timer(const Duration(milliseconds: 500), () {
        _validateClub(query);
      });
    }
  }

  Future<void> _validateClub(String query) async {
    if (!mounted) return;

    setState(() {
      _validationState = ValidationState.validating;
    });

    final result = await _apiService.validateClub(widget.sport, query);

    if (!mounted) return;

    setState(() {
      if (result.valid) {
        _validationState = ValidationState.valid;
        _normalizedName = result.normalizedName;
        _validationError = null;
      } else {
        _validationState = ValidationState.invalid;
        _validationError = result.error ?? 'Team not found';
        _normalizedName = null;
      }
    });
  }

  void _onFocusChanged() {
    if (!_focusNode.hasFocus) {
      Future.delayed(const Duration(milliseconds: 200), () {
        _showSuggestions = false;
        _removeOverlay();
      });
    }
  }

  void _updateOverlay() {
    _removeOverlay();
    if (_showSuggestions && _focusNode.hasFocus) {
      _overlayEntry = _createOverlayEntry();
      Overlay.of(context).insert(_overlayEntry!);
    }
  }

  void _removeOverlay() {
    _overlayEntry?.remove();
    _overlayEntry = null;
  }

  OverlayEntry _createOverlayEntry() {
    final renderBox = context.findRenderObject() as RenderBox;
    final size = renderBox.size;

    return OverlayEntry(
      builder: (context) => Positioned(
        width: size.width,
        child: CompositedTransformFollower(
          link: _layerLink,
          showWhenUnlinked: false,
          offset: Offset(0, size.height + 4),
          child: Material(
            elevation: 8,
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(AppTheme.radiusMd),
            child: Container(
              constraints: const BoxConstraints(maxHeight: 200),
              decoration: BoxDecoration(
                border: Border.all(color: AppColors.gray700),
                borderRadius: BorderRadius.circular(AppTheme.radiusMd),
              ),
              child: ListView.builder(
                shrinkWrap: true,
                padding: EdgeInsets.zero,
                itemCount: _filteredSuggestions.length,
                itemBuilder: (context, index) {
                  final club = _filteredSuggestions[index];
                  return InkWell(
                    onTap: () {
                      _controller.text = club.displayName;
                      _showSuggestions = false;
                      _removeOverlay();
                      setState(() {
                        _validationState = ValidationState.valid;
                        _normalizedName = club.fullName;
                        _validationError = null;
                      });
                      _focusNode.unfocus();
                      widget.onSubmitted?.call(club.displayName);
                    },
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppTheme.spaceMd,
                        vertical: AppTheme.spaceSm,
                      ),
                      child: Row(
                        children: [
                          if (club.badge != null || club.logo != null)
                            Padding(
                              padding: const EdgeInsets.only(right: AppTheme.spaceSm),
                              child: Image.network(
                                getProxiedImageUrl(club.badge ?? club.logo!) ?? '',
                                width: 24,
                                height: 24,
                                errorBuilder: (_, __, ___) => const Icon(
                                  Icons.sports,
                                  size: 24,
                                  color: AppColors.textSecondary,
                                ),
                              ),
                            ),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  club.displayName,
                                  style: AppTheme.bodyStyle,
                                ),
                                if (club.country != null || club.abbreviation != null)
                                  Text(
                                    club.country ?? club.abbreviation!,
                                    style: AppTheme.captionStyle.copyWith(
                                      color: AppColors.textSecondary,
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _handleSubmit() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;

    // Only allow submission when validation is complete and valid
    if (_validationState != ValidationState.valid) {
      String errorMsg;
      switch (_validationState) {
        case ValidationState.invalid:
          errorMsg = _validationError ?? 'Team not found';
          break;
        case ValidationState.validating:
          errorMsg = 'Validating team...';
          break;
        case ValidationState.idle:
          errorMsg = 'Please enter a valid team name';
          break;
        case ValidationState.valid:
          errorMsg = ''; // Won't reach here
          break;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(errorMsg),
          backgroundColor: AppColors.error,
          duration: const Duration(seconds: 2),
        ),
      );
      return;
    }

    // Submit with normalized name (guaranteed to exist when valid)
    widget.onSubmitted?.call(_normalizedName ?? text);
  }

  Color get _borderColor {
    switch (_validationState) {
      case ValidationState.valid:
        return AppColors.success;
      case ValidationState.invalid:
        return AppColors.error;
      case ValidationState.validating:
        return AppColors.primary;
      case ValidationState.idle:
        return AppColors.gray700;
    }
  }

  Widget? get _suffixIcon {
    if (!widget.enabled) return null;

    switch (_validationState) {
      case ValidationState.validating:
        return const Padding(
          padding: EdgeInsets.all(12),
          child: SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: AppColors.primary,
            ),
          ),
        );
      case ValidationState.valid:
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.check_circle, color: AppColors.success, size: 20),
            IconButton(
              icon: const Icon(Icons.send),
              color: AppColors.primary,
              onPressed: _handleSubmit,
            ),
          ],
        );
      case ValidationState.invalid:
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: AppColors.error, size: 20),
            IconButton(
              icon: const Icon(Icons.send),
              color: AppColors.textSecondary,
              onPressed: _handleSubmit,
            ),
          ],
        );
      case ValidationState.idle:
        return IconButton(
          icon: const Icon(Icons.send),
          color: AppColors.primary,
          onPressed: _handleSubmit,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (widget.label != null) ...[
          Text(
            widget.label!,
            style: AppTheme.captionStyle.copyWith(
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: AppTheme.spaceSm),
        ],
        CompositedTransformTarget(
          link: _layerLink,
          child: TextField(
            controller: _controller,
            focusNode: _focusNode,
            enabled: widget.enabled,
            autofocus: widget.autofocus,
            textCapitalization: TextCapitalization.words,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _handleSubmit(),
            decoration: InputDecoration(
              hintText: widget.hint ?? 'Enter team name...',
              suffixIcon: _suffixIcon,
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppTheme.radiusMd),
                borderSide: BorderSide(color: _borderColor, width: 1.5),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppTheme.radiusMd),
                borderSide: BorderSide(color: _borderColor, width: 2),
              ),
            ),
          ),
        ),
        // Validation message
        if (_validationState == ValidationState.valid && _normalizedName != null)
          Padding(
            padding: const EdgeInsets.only(top: AppTheme.spaceXs),
            child: Text(
              _normalizedName!,
              style: AppTheme.captionStyle.copyWith(
                color: AppColors.success,
              ),
            ),
          ).animate().fadeIn(),
        if (_validationState == ValidationState.invalid && _validationError != null)
          Padding(
            padding: const EdgeInsets.only(top: AppTheme.spaceXs),
            child: Text(
              _validationError!,
              style: AppTheme.captionStyle.copyWith(
                color: AppColors.error,
              ),
            ),
          ).animate().fadeIn().shake(hz: 3, duration: 300.ms),
      ],
    );
  }
}

/// Card showing club submission status
class ClubSubmissionCard extends StatelessWidget {
  final String title;
  final bool isSubmitted;
  final String? submittedClub;
  final String? submittedClubBadge;
  final bool isLoading;
  final Widget? input;

  const ClubSubmissionCard({
    super.key,
    required this.title,
    required this.isSubmitted,
    this.submittedClub,
    this.submittedClubBadge,
    this.isLoading = false,
    this.input,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceMd),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        border: Border.all(
          color: isSubmitted ? AppColors.success : AppColors.gray700,
          width: isSubmitted ? 2 : 1,
        ),
        boxShadow: isSubmitted ? AppTheme.glowShadow(AppColors.success) : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Text(
                title,
                style: AppTheme.captionStyle.copyWith(
                  letterSpacing: 2,
                  color: isSubmitted ? AppColors.success : AppColors.textSecondary,
                ),
              ),
              const Spacer(),
              if (isSubmitted)
                const Icon(
                  Icons.check_circle,
                  color: AppColors.success,
                  size: 20,
                )
                    .animate()
                    .fadeIn()
                    .scale(begin: const Offset(0.5, 0.5), end: const Offset(1, 1)),
              if (isLoading)
                const _WaitingDots(),
            ],
          ),
          const SizedBox(height: AppTheme.spaceMd),
          if (isSubmitted && submittedClub != null)
            Row(
              children: [
                // Club badge
                if (submittedClubBadge != null)
                  Container(
                    width: 48,
                    height: 48,
                    margin: const EdgeInsets.only(right: AppTheme.spaceMd),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: AppColors.surfaceLight,
                      border: Border.all(
                        color: AppColors.success.withValues(alpha: 0.3),
                        width: 2,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: AppColors.success.withValues(alpha: 0.2),
                          blurRadius: 12,
                        ),
                      ],
                    ),
                    child: ClipOval(
                      child: Image.network(
                        getProxiedImageUrl(submittedClubBadge) ?? '',
                        width: 48,
                        height: 48,
                        fit: BoxFit.contain,
                        errorBuilder: (_, __, ___) => Icon(
                          Icons.sports_soccer,
                          color: AppColors.success,
                          size: 24,
                        ),
                      ),
                    ),
                  )
                      .animate()
                      .fadeIn()
                      .scale(
                        begin: const Offset(0.5, 0.5),
                        end: const Offset(1, 1),
                        curve: Curves.elasticOut,
                      ),
                // Club name
                Expanded(
                  child: Text(
                    submittedClub!,
                    style: AppTheme.h3Style.copyWith(
                      color: AppColors.success,
                    ),
                  ),
                ),
              ],
            )
          else if (isLoading)
            Text(
              'Waiting...',
              style: AppTheme.bodyStyle.copyWith(
                color: AppColors.textSecondary,
                fontStyle: FontStyle.italic,
              ),
            )
          else if (input != null)
            input!,
        ],
      ),
    );
  }
}

/// Animated waiting dots
class _WaitingDots extends StatelessWidget {
  const _WaitingDots();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (index) {
        return Container(
          width: 6,
          height: 6,
          margin: const EdgeInsets.symmetric(horizontal: 2),
          decoration: const BoxDecoration(
            color: AppColors.textSecondary,
            shape: BoxShape.circle,
          ),
        )
            .animate(
              onPlay: (controller) => controller.repeat(),
            )
            .fadeIn(delay: Duration(milliseconds: index * 200))
            .then()
            .fadeOut(delay: const Duration(milliseconds: 400));
      }),
    );
  }
}
