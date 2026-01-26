import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';

/// Input field for guessing player names
/// Features shake animation on wrong guess
class GuessInput extends StatefulWidget {
  final ValueChanged<String>? onSubmitted;
  final bool enabled;
  final bool autofocus;
  final bool showError;
  final String? hint;

  const GuessInput({
    super.key,
    this.onSubmitted,
    this.enabled = true,
    this.autofocus = true,
    this.showError = false,
    this.hint,
  });

  @override
  State<GuessInput> createState() => _GuessInputState();
}

class _GuessInputState extends State<GuessInput>
    with SingleTickerProviderStateMixin {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  late AnimationController _shakeController;
  bool _isShaking = false;

  @override
  void initState() {
    super.initState();
    _shakeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
  }

  @override
  void didUpdateWidget(GuessInput oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.showError && !oldWidget.showError) {
      _triggerShake();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    _shakeController.dispose();
    super.dispose();
  }

  void _triggerShake() {
    setState(() => _isShaking = true);
    _shakeController.forward().then((_) {
      _shakeController.reset();
      if (mounted) {
        setState(() => _isShaking = false);
        _controller.clear();
        _focusNode.requestFocus();
      }
    });
  }

  void _handleSubmit() {
    final text = _controller.text.trim();
    if (text.isNotEmpty && widget.enabled) {
      widget.onSubmitted?.call(text);
    }
  }

  @override
  Widget build(BuildContext context) {
    Widget input = TextField(
      controller: _controller,
      focusNode: _focusNode,
      enabled: widget.enabled,
      autofocus: widget.autofocus,
      textCapitalization: TextCapitalization.words,
      textInputAction: TextInputAction.send,
      style: AppTheme.h3Style.copyWith(fontSize: 20),
      onSubmitted: (_) => _handleSubmit(),
      decoration: InputDecoration(
        hintText: widget.hint ?? 'Enter player name...',
        hintStyle: AppTheme.bodyStyle.copyWith(
          color: AppColors.textSecondary,
          fontSize: 20,
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppTheme.spaceLg,
          vertical: AppTheme.spaceMd,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppTheme.radiusLg),
          borderSide: BorderSide(
            color: _isShaking ? AppColors.error : AppColors.gray700,
            width: 2,
          ),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppTheme.radiusLg),
          borderSide: const BorderSide(
            color: AppColors.gray700,
            width: 2,
          ),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppTheme.radiusLg),
          borderSide: BorderSide(
            color: _isShaking ? AppColors.error : AppColors.primary,
            width: 2,
          ),
        ),
        suffixIcon: widget.enabled
            ? IconButton(
                icon: const Icon(Icons.send, size: 28),
                color: AppColors.primary,
                onPressed: _handleSubmit,
              )
            : null,
      ),
    );

    // Apply shake animation
    if (_isShaking) {
      input = input
          .animate(controller: _shakeController)
          .shake(hz: 6, rotation: 0)
          .tint(color: AppColors.error.withValues(alpha: 0.3));
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        input,
        if (_isShaking)
          Padding(
            padding: const EdgeInsets.only(top: AppTheme.spaceSm),
            child: Text(
              'Wrong! Try again',
              style: AppTheme.captionStyle.copyWith(
                color: AppColors.error,
              ),
            ),
          ).animate().fadeIn().slideY(begin: -0.2, end: 0),
      ],
    );
  }
}

/// Large submit button with glow effect
class SubmitGuessButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final bool enabled;
  final String label;

  const SubmitGuessButton({
    super.key,
    this.onPressed,
    this.enabled = true,
    this.label = 'SUBMIT GUESS',
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: AppTheme.fastDuration,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        boxShadow: enabled
            ? [
                BoxShadow(
                  color: AppColors.success.withValues(alpha: 0.4),
                  blurRadius: 20,
                  spreadRadius: 0,
                ),
              ]
            : null,
      ),
      child: SizedBox(
        width: double.infinity,
        height: 56,
        child: ElevatedButton(
          onPressed: enabled ? onPressed : null,
          style: ElevatedButton.styleFrom(
            backgroundColor: enabled ? AppColors.success : AppColors.gray700,
            foregroundColor: enabled ? AppColors.voidBlack : AppColors.textSecondary,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(AppTheme.radiusLg),
            ),
          ),
          child: Text(
            label,
            style: AppTheme.h3Style.copyWith(
              color: enabled ? AppColors.voidBlack : AppColors.textSecondary,
              fontSize: 18,
            ),
          ),
        ),
      ),
    );
  }
}
