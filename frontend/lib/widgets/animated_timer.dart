import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';

/// Circular countdown timer with urgency effects
/// The signature UI element of the game
class AnimatedTimer extends StatefulWidget {
  final int remainingSeconds;
  final int totalSeconds;
  final double size;
  final VoidCallback? onComplete;

  const AnimatedTimer({
    super.key,
    required this.remainingSeconds,
    this.totalSeconds = 60,
    this.size = 200,
    this.onComplete,
  });

  @override
  State<AnimatedTimer> createState() => _AnimatedTimerState();
}

class _AnimatedTimerState extends State<AnimatedTimer>
    with SingleTickerProviderStateMixin {
  late AnimationController _shakeController;

  @override
  void initState() {
    super.initState();
    _shakeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 100),
    );
  }

  @override
  void didUpdateWidget(AnimatedTimer oldWidget) {
    super.didUpdateWidget(oldWidget);

    // Trigger shake when time is critical
    if (widget.remainingSeconds <= 5 && widget.remainingSeconds > 0) {
      _shakeController.forward().then((_) => _shakeController.reverse());
    }

    // Call onComplete when timer reaches 0
    if (widget.remainingSeconds == 0 && oldWidget.remainingSeconds != 0) {
      widget.onComplete?.call();
    }
  }

  @override
  void dispose() {
    _shakeController.dispose();
    super.dispose();
  }

  int get _urgencyLevel {
    if (widget.remainingSeconds > 30) return 0;
    if (widget.remainingSeconds > 15) return 1;
    if (widget.remainingSeconds > 5) return 2;
    return 3; // Critical
  }

  Color get _timerColor {
    switch (_urgencyLevel) {
      case 0:
        return AppColors.timerCalm;
      case 1:
        return AppColors.timerWarning;
      case 2:
      case 3:
      default:
        return AppColors.timerUrgent;
    }
  }

  Duration get _pulseDuration {
    switch (_urgencyLevel) {
      case 0:
        return Duration.zero;
      case 1:
        return const Duration(milliseconds: 1000);
      case 2:
        return const Duration(milliseconds: 500);
      case 3:
      default:
        return const Duration(milliseconds: 250);
    }
  }

  @override
  Widget build(BuildContext context) {
    final progress = widget.remainingSeconds / widget.totalSeconds;

    Widget timer = AnimatedBuilder(
      animation: _shakeController,
      builder: (context, child) {
        final shake = math.sin(_shakeController.value * math.pi * 4) * 3;
        return Transform.translate(
          offset: Offset(shake, 0),
          child: child,
        );
      },
      child: SizedBox(
        width: widget.size,
        height: widget.size,
        child: Stack(
          alignment: Alignment.center,
          children: [
            // Background circle
            CustomPaint(
              size: Size(widget.size, widget.size),
              painter: _TimerBackgroundPainter(
                color: AppColors.surface,
                strokeWidth: 8,
              ),
            ),
            // Progress arc
            TweenAnimationBuilder<double>(
              tween: Tween(begin: progress, end: progress),
              duration: const Duration(milliseconds: 200),
              curve: Curves.easeOut,
              builder: (context, value, child) {
                return CustomPaint(
                  size: Size(widget.size, widget.size),
                  painter: _TimerProgressPainter(
                    progress: value,
                    color: _timerColor,
                    strokeWidth: 8,
                    glowColor: _timerColor.withValues(alpha: 0.5),
                  ),
                );
              },
            ),
            // Time display
            Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  widget.remainingSeconds.toString(),
                  style: AppTheme.timerStyle.copyWith(
                    color: _timerColor,
                    fontSize: widget.size * 0.35,
                  ),
                ),
                Text(
                  'SECONDS',
                  style: AppTheme.captionStyle.copyWith(
                    color: _timerColor.withValues(alpha: 0.7),
                    letterSpacing: 2,
                    fontSize: widget.size * 0.06,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );

    // Add pulsing effect for urgency
    if (_urgencyLevel > 0) {
      timer = timer
          .animate(
            onPlay: (controller) => controller.repeat(reverse: true),
          )
          .scale(
            begin: const Offset(1, 1),
            end: Offset(1 + (_urgencyLevel * 0.02), 1 + (_urgencyLevel * 0.02)),
            duration: _pulseDuration,
            curve: Curves.easeInOut,
          );
    }

    // Add glow effect
    return Container(
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: _timerColor.withValues(alpha: 0.3),
            blurRadius: 30 + (_urgencyLevel * 10).toDouble(),
            spreadRadius: _urgencyLevel * 2,
          ),
        ],
      ),
      child: timer,
    );
  }
}

class _TimerBackgroundPainter extends CustomPainter {
  final Color color;
  final double strokeWidth;

  _TimerBackgroundPainter({
    required this.color,
    required this.strokeWidth,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;

    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width - strokeWidth) / 2;

    canvas.drawCircle(center, radius, paint);
  }

  @override
  bool shouldRepaint(covariant _TimerBackgroundPainter oldDelegate) {
    return color != oldDelegate.color || strokeWidth != oldDelegate.strokeWidth;
  }
}

class _TimerProgressPainter extends CustomPainter {
  final double progress;
  final Color color;
  final double strokeWidth;
  final Color glowColor;

  _TimerProgressPainter({
    required this.progress,
    required this.color,
    required this.strokeWidth,
    required this.glowColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width - strokeWidth) / 2;

    // Glow effect
    final glowPaint = Paint()
      ..color = glowColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth + 4
      ..strokeCap = StrokeCap.round
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);

    // Main arc
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;

    final startAngle = -math.pi / 2;
    final sweepAngle = 2 * math.pi * progress;

    final rect = Rect.fromCircle(center: center, radius: radius);

    // Draw glow
    canvas.drawArc(rect, startAngle, sweepAngle, false, glowPaint);
    // Draw arc
    canvas.drawArc(rect, startAngle, sweepAngle, false, paint);
  }

  @override
  bool shouldRepaint(covariant _TimerProgressPainter oldDelegate) {
    return progress != oldDelegate.progress ||
        color != oldDelegate.color ||
        strokeWidth != oldDelegate.strokeWidth;
  }
}

/// Compact timer for header display
class CompactTimer extends StatelessWidget {
  final int remainingSeconds;

  const CompactTimer({
    super.key,
    required this.remainingSeconds,
  });

  Color get _color {
    if (remainingSeconds > 30) return AppColors.timerCalm;
    if (remainingSeconds > 15) return AppColors.timerWarning;
    return AppColors.timerUrgent;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppTheme.spaceMd,
        vertical: AppTheme.spaceSm,
      ),
      decoration: BoxDecoration(
        color: _color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(AppTheme.radiusFull),
        border: Border.all(color: _color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.timer, color: _color, size: 20),
          const SizedBox(width: AppTheme.spaceSm),
          Text(
            '${remainingSeconds}s',
            style: AppTheme.scoreStyle.copyWith(
              color: _color,
              fontSize: 20,
            ),
          ),
        ],
      ),
    );
  }
}
