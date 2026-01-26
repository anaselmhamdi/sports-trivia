import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:share_plus/share_plus.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';

/// Displays the room code with copy and share functionality
/// Features typewriter reveal animation on entry
class RoomCodeDisplay extends StatefulWidget {
  final String roomCode;
  final bool showShareButton;
  final bool animate;

  const RoomCodeDisplay({
    super.key,
    required this.roomCode,
    this.showShareButton = true,
    this.animate = true,
  });

  @override
  State<RoomCodeDisplay> createState() => _RoomCodeDisplayState();
}

class _RoomCodeDisplayState extends State<RoomCodeDisplay> {
  bool _copied = false;

  Future<void> _copyToClipboard() async {
    await Clipboard.setData(ClipboardData(text: widget.roomCode));
    setState(() => _copied = true);

    // Reset after 2 seconds
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        setState(() => _copied = false);
      }
    });
  }

  Future<void> _shareCode() async {
    await Share.share(
      'Join my Clutch game! Room code: ${widget.roomCode}',
      subject: 'Clutch - Game Invite',
    );
  }

  @override
  Widget build(BuildContext context) {
    Widget codeDisplay = GestureDetector(
      onTap: _copyToClipboard,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppTheme.spaceLg,
          vertical: AppTheme.spaceMd,
        ),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(AppTheme.radiusLg),
          border: Border.all(
            color: _copied ? AppColors.success : AppColors.primary,
            width: 2,
          ),
          boxShadow: AppTheme.glowShadow(
            _copied ? AppColors.success : AppColors.primary,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Room code with letter spacing
            Text(
              widget.roomCode,
              style: AppTheme.codeStyle.copyWith(
                letterSpacing: 8,
              ),
            ),
            const SizedBox(width: AppTheme.spaceMd),
            // Copy indicator
            AnimatedSwitcher(
              duration: AppTheme.fastDuration,
              child: Icon(
                _copied ? Icons.check : Icons.copy,
                key: ValueKey(_copied),
                color: _copied ? AppColors.success : AppColors.primary,
                size: 24,
              ),
            ),
          ],
        ),
      ),
    );

    // Apply typewriter animation if enabled
    if (widget.animate) {
      codeDisplay = codeDisplay
          .animate()
          .fadeIn(duration: AppTheme.normalDuration)
          .slideY(begin: 0.2, end: 0, curve: Curves.easeOutCubic);
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          'ROOM CODE',
          style: AppTheme.captionStyle.copyWith(
            letterSpacing: 2,
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: AppTheme.spaceMd),
        codeDisplay,
        if (_copied)
          Padding(
            padding: const EdgeInsets.only(top: AppTheme.spaceSm),
            child: Text(
              'Copied to clipboard!',
              style: AppTheme.captionStyle.copyWith(
                color: AppColors.success,
              ),
            ),
          )
              .animate()
              .fadeIn(duration: AppTheme.fastDuration)
              .slideY(begin: -0.2, end: 0),
        if (widget.showShareButton) ...[
          const SizedBox(height: AppTheme.spaceLg),
          OutlinedButton.icon(
            onPressed: _shareCode,
            icon: const Icon(Icons.share),
            label: const Text('Share Invite'),
          ),
        ],
      ],
    );
  }
}

/// Compact room code display for headers
class CompactRoomCode extends StatelessWidget {
  final String roomCode;

  const CompactRoomCode({
    super.key,
    required this.roomCode,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppTheme.spaceMd,
        vertical: AppTheme.spaceSm,
      ),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusFull),
        border: Border.all(color: AppColors.gray700),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.meeting_room,
            size: 16,
            color: AppColors.textSecondary,
          ),
          const SizedBox(width: AppTheme.spaceSm),
          Text(
            roomCode,
            style: AppTheme.captionStyle.copyWith(
              fontFamily: 'JetBrains Mono',
              letterSpacing: 2,
            ),
          ),
        ],
      ),
    );
  }
}
