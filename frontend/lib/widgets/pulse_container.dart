import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';

/// A container that pulses with a glow effect
/// Used for creating urgency and highlighting active elements
class PulseContainer extends StatefulWidget {
  final Widget child;
  final Color glowColor;
  final bool isPulsing;
  final Duration pulseDuration;
  final double pulseScale;
  final BorderRadius? borderRadius;
  final EdgeInsetsGeometry? padding;
  final Color? backgroundColor;
  final Border? border;

  const PulseContainer({
    super.key,
    required this.child,
    this.glowColor = AppColors.primary,
    this.isPulsing = false,
    this.pulseDuration = const Duration(milliseconds: 1000),
    this.pulseScale = 1.05,
    this.borderRadius,
    this.padding,
    this.backgroundColor,
    this.border,
  });

  @override
  State<PulseContainer> createState() => _PulseContainerState();
}

class _PulseContainerState extends State<PulseContainer>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;
  late Animation<double> _opacityAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: widget.pulseDuration,
    );

    _scaleAnimation = Tween<double>(
      begin: 1.0,
      end: widget.pulseScale,
    ).animate(CurvedAnimation(
      parent: _controller,
      curve: Curves.easeInOut,
    ));

    _opacityAnimation = Tween<double>(
      begin: 1.0,
      end: 0.7,
    ).animate(CurvedAnimation(
      parent: _controller,
      curve: Curves.easeInOut,
    ));

    if (widget.isPulsing) {
      _controller.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(PulseContainer oldWidget) {
    super.didUpdateWidget(oldWidget);

    if (widget.isPulsing != oldWidget.isPulsing) {
      if (widget.isPulsing) {
        _controller.repeat(reverse: true);
      } else {
        _controller.stop();
        _controller.reset();
      }
    }

    if (widget.pulseDuration != oldWidget.pulseDuration) {
      _controller.duration = widget.pulseDuration;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Transform.scale(
          scale: widget.isPulsing ? _scaleAnimation.value : 1.0,
          child: Container(
            padding: widget.padding,
            decoration: BoxDecoration(
              color: widget.backgroundColor ?? AppColors.surface,
              borderRadius: widget.borderRadius ?? BorderRadius.circular(AppTheme.radiusLg),
              border: widget.border ??
                  Border.all(
                    color: widget.glowColor.withValues(
                      alpha: widget.isPulsing ? _opacityAnimation.value : 1.0,
                    ),
                    width: 2,
                  ),
              boxShadow: widget.isPulsing
                  ? [
                      BoxShadow(
                        color: widget.glowColor.withValues(
                          alpha: 0.3 * _opacityAnimation.value,
                        ),
                        blurRadius: 20,
                        spreadRadius: 0,
                      ),
                      BoxShadow(
                        color: widget.glowColor.withValues(
                          alpha: 0.1 * _opacityAnimation.value,
                        ),
                        blurRadius: 40,
                        spreadRadius: 0,
                      ),
                    ]
                  : null,
            ),
            child: child,
          ),
        );
      },
      child: widget.child,
    );
  }
}

/// A border that pulses with urgency
class UrgencyBorder extends StatelessWidget {
  final Widget child;
  final int urgencyLevel; // 0 = calm, 1 = warning, 2 = urgent
  final BorderRadius? borderRadius;

  const UrgencyBorder({
    super.key,
    required this.child,
    required this.urgencyLevel,
    this.borderRadius,
  });

  @override
  Widget build(BuildContext context) {
    final Color glowColor;
    final Duration pulseDuration;
    final bool isPulsing;

    switch (urgencyLevel) {
      case 0:
        glowColor = AppColors.timerCalm;
        pulseDuration = const Duration(milliseconds: 2000);
        isPulsing = false;
        break;
      case 1:
        glowColor = AppColors.timerWarning;
        pulseDuration = const Duration(milliseconds: 1000);
        isPulsing = true;
        break;
      case 2:
      default:
        glowColor = AppColors.timerUrgent;
        pulseDuration = const Duration(milliseconds: 500);
        isPulsing = true;
        break;
    }

    return PulseContainer(
      glowColor: glowColor,
      isPulsing: isPulsing,
      pulseDuration: pulseDuration,
      borderRadius: borderRadius,
      child: child,
    );
  }
}
