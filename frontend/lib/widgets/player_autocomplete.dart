import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../utils/image_helpers.dart';

/// Autocomplete input for NBA player names. Loads the roster once on first
/// use and reuses it across builds. Shows the player's headshot next to each
/// suggestion so the user recognizes the pick at a glance.
class PlayerAutocomplete extends StatefulWidget {
  final String sport; // "nba"
  final String hintText;
  final void Function(String name) onSubmitted;
  final VoidCallback? onCancelled;
  final bool autofocus;

  const PlayerAutocomplete({
    super.key,
    required this.sport,
    required this.onSubmitted,
    this.hintText = 'NBA player name',
    this.onCancelled,
    this.autofocus = true,
  });

  @override
  State<PlayerAutocomplete> createState() => _PlayerAutocompleteState();
}

class _PlayerAutocompleteState extends State<PlayerAutocomplete> {
  static List<PlayerInfo>? _cachedNba;
  List<PlayerInfo> _players = const [];

  @override
  void initState() {
    super.initState();
    _loadPlayers();
  }

  Future<void> _loadPlayers() async {
    if (_cachedNba != null) {
      setState(() => _players = _cachedNba!);
      return;
    }
    final list = await ApiService().getPlayers(widget.sport);
    _cachedNba = list;
    if (mounted) setState(() => _players = list);
  }

  Iterable<PlayerInfo> _filter(TextEditingValue value) {
    final q = value.text.trim().toLowerCase();
    if (q.isEmpty) return const Iterable.empty();
    // Prefer prefix matches (name starts with query) first, then substring.
    final prefix = <PlayerInfo>[];
    final contains = <PlayerInfo>[];
    for (final p in _players) {
      final n = p.name.toLowerCase();
      if (n.startsWith(q)) {
        prefix.add(p);
      } else if (n.contains(q)) {
        contains.add(p);
      }
      if (prefix.length >= 8) break;
    }
    return [...prefix, ...contains].take(8);
  }

  @override
  Widget build(BuildContext context) {
    return RawAutocomplete<PlayerInfo>(
      displayStringForOption: (p) => p.name,
      optionsBuilder: _filter,
      onSelected: (p) => widget.onSubmitted(p.name),
      // Input lives near the bottom of the grid board — open suggestions
      // upward so they don't fall off-screen.
      optionsViewOpenDirection: OptionsViewOpenDirection.up,
      fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) {
        if (widget.autofocus && !focusNode.hasFocus) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted && !focusNode.hasFocus) focusNode.requestFocus();
          });
        }
        return TextField(
          controller: controller,
          focusNode: focusNode,
          textCapitalization: TextCapitalization.words,
          onSubmitted: (v) {
            final text = v.trim();
            if (text.isEmpty) return;
            widget.onSubmitted(text);
          },
          decoration: InputDecoration(
            hintText: widget.hintText,
            prefixIcon: const Icon(Icons.sports_basketball),
            suffixIcon: controller.text.isEmpty
                ? null
                : IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () {
                      controller.clear();
                      widget.onCancelled?.call();
                    },
                  ),
          ),
        );
      },
      optionsViewBuilder: (context, onSelected, options) {
        const double itemHeight = 52.0;
        final optionList = options.toList(growable: false);
        final visibleItems = optionList.length.clamp(1, 5);
        return Align(
          alignment: Alignment.bottomLeft,
          child: Material(
            elevation: 6,
            borderRadius: BorderRadius.circular(AppTheme.radiusMd),
            color: AppColors.surface,
            clipBehavior: Clip.antiAlias,
            child: SizedBox(
              width: 380,
              height: itemHeight * visibleItems,
              child: ListView.builder(
                padding: EdgeInsets.zero,
                itemCount: optionList.length,
                itemExtent: itemHeight,
                itemBuilder: (context, i) {
                  final p = optionList[i];
                  return _SuggestionTile(
                    player: p,
                    onTap: () => onSelected(p),
                  );
                },
              ),
            ),
          ),
        );
      },
    );
  }
}

class _SuggestionTile extends StatelessWidget {
  final PlayerInfo player;
  final VoidCallback onTap;
  const _SuggestionTile({required this.player, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final url = getProxiedImageUrl(player.headshotUrl);
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppTheme.spaceSm,
        ),
        child: Row(
          children: [
            _Headshot(url: url),
            const SizedBox(width: AppTheme.spaceSm),
            Expanded(
              child: Text(
                player.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Headshot extends StatelessWidget {
  final String? url;
  const _Headshot({required this.url});

  @override
  Widget build(BuildContext context) {
    const size = 36.0;
    final placeholder = Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        color: AppColors.gray700,
        shape: BoxShape.circle,
      ),
      child: const Icon(Icons.person, color: AppColors.textSecondary, size: 20),
    );
    if (url == null) return placeholder;
    return ClipOval(
      child: Image.network(
        url!,
        width: size,
        height: size,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => placeholder,
      ),
    );
  }
}
