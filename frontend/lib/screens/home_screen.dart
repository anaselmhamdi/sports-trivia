import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../models/game_state.dart';
import '../providers/game_provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../widgets/sport_selector.dart';

/// Home screen for creating or joining games
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _nameController = TextEditingController();
  final _roomCodeController = TextEditingController();
  SportType _selectedSport = SportType.soccer;
  GameMode _selectedMode = GameMode.classic;
  int _maxPlayers = 4;
  bool _isCreating = false;
  bool _isJoining = false;

  @override
  void dispose() {
    _nameController.dispose();
    _roomCodeController.dispose();
    super.dispose();
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppColors.error,
      ),
    );
    setState(() {
      _isCreating = false;
      _isJoining = false;
    });
  }

  Future<void> _createRoom() async {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      _showError('Please enter your name');
      return;
    }

    setState(() => _isCreating = true);
    await ref.read(gameStateProvider.notifier).createRoom(
      name,
      _selectedSport,
      mode: _selectedMode,
      maxPlayers: _selectedMode == GameMode.multiplayer ? _maxPlayers : 2,
    );
  }

  Future<void> _joinRoom() async {
    final name = _nameController.text.trim();
    final code = _roomCodeController.text.trim().toUpperCase();

    if (name.isEmpty) {
      _showError('Please enter your name');
      return;
    }
    if (code.isEmpty || code.length != 4) {
      _showError('Please enter a valid 4-character room code');
      return;
    }

    setState(() => _isJoining = true);
    await ref.read(gameStateProvider.notifier).joinRoom(code, name);
  }

  @override
  Widget build(BuildContext context) {
    // Watch for state changes (triggers rebuilds, navigation handled by ref.listen below)
    ref.watch(gameStateProvider);
    final screenWidth = MediaQuery.of(context).size.width;
    final isWide = screenWidth > 600;

    // Navigate based on phase changes
    ref.listen<GameState>(gameStateProvider, (previous, next) {
      // Show errors
      if (next.errorMessage != null && next.errorMessage!.isNotEmpty) {
        _showError(next.errorMessage!);
        ref.read(gameStateProvider.notifier).clearError();
      }

      // Navigate to appropriate screen based on phase (use post-frame to avoid navigation during build)
      if (previous?.phase != next.phase) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          if (next.phase == GamePhase.clubSelection || next.phase == GamePhase.guessing) {
            context.goNamed('game');
          } else if (next.phase == GamePhase.lobby) {
            context.goNamed('lobby');
          } else if (next.phase == GamePhase.results) {
            context.goNamed('result');
          }
        });
      }
    });

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppTheme.spaceLg),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 500),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(height: AppTheme.space2xl),

                  // Logo / Title
                  _buildTitle(),

                  const SizedBox(height: AppTheme.space3xl),

                  // Name input
                  _buildNameInput(),

                  const SizedBox(height: AppTheme.spaceLg),

                  // Sport selector
                  _buildSportSelector(),

                  const SizedBox(height: AppTheme.spaceLg),

                  // Mode selector
                  _buildModeSelector(),

                  const SizedBox(height: AppTheme.space2xl),

                  // Action cards
                  if (isWide)
                    Row(
                      children: [
                        Expanded(child: _buildCreateCard()),
                        const SizedBox(width: AppTheme.spaceMd),
                        Expanded(child: _buildJoinCard()),
                      ],
                    )
                  else ...[
                    _buildCreateCard(),
                    const SizedBox(height: AppTheme.spaceMd),
                    _buildJoinCard(),
                  ],

                  const SizedBox(height: AppTheme.space2xl),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTitle() {
    return Column(
      children: [
        Text(
          'CLUTCH',
          style: AppTheme.heroStyle.copyWith(
            color: AppColors.primary,
            height: 1,
          ),
        )
            .animate()
            .fadeIn(duration: AppTheme.normalDuration)
            .slideY(begin: -0.3, end: 0),
        const SizedBox(height: AppTheme.spaceMd),
        Text(
          'think you know sports?',
          style: AppTheme.captionStyle.copyWith(
            color: AppColors.textSecondary,
            letterSpacing: 1,
          ),
        )
            .animate()
            .fadeIn(delay: const Duration(milliseconds: 100))
            .slideY(begin: -0.3, end: 0),
        const SizedBox(height: AppTheme.spaceXs),
        Text(
          'go head to head to find out.',
          style: AppTheme.captionStyle.copyWith(
            color: AppColors.textSecondary,
            letterSpacing: 1,
          ),
        )
            .animate()
            .fadeIn(delay: const Duration(milliseconds: 200))
            .slideY(begin: -0.3, end: 0),
      ],
    );
  }

  Widget _buildNameInput() {
    return TextField(
      controller: _nameController,
      textCapitalization: TextCapitalization.words,
      textAlign: TextAlign.center,
      style: AppTheme.h3Style.copyWith(fontSize: 18),
      decoration: InputDecoration(
        hintText: 'Enter your name',
        hintStyle: AppTheme.bodyStyle.copyWith(
          color: AppColors.textSecondary,
        ),
        prefixIcon: const Icon(Icons.person_outline, color: AppColors.textSecondary),
        filled: true,
        fillColor: AppColors.surface,
      ),
    ).animate().fadeIn(delay: const Duration(milliseconds: 300));
  }

  Widget _buildSportSelector() {
    return SportSelector(
      selectedSport: _selectedSport,
      onSportChanged: (sport) {
        setState(() {
          _selectedSport = sport;
          // NBA Grid is NBA-only — revert to classic if soccer is chosen.
          if (sport != SportType.nba && _selectedMode == GameMode.nbaGrid) {
            _selectedMode = GameMode.classic;
            ref.read(gameStateProvider.notifier).setMode(GameMode.classic);
          }
        });
        ref.read(gameStateProvider.notifier).setSport(sport);
      },
    ).animate().fadeIn(delay: const Duration(milliseconds: 400));
  }

  Widget _buildModeSelector() {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceSm),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        border: Border.all(color: AppColors.gray700),
      ),
      child: Wrap(
        alignment: WrapAlignment.center,
        spacing: AppTheme.spaceSm,
        runSpacing: AppTheme.spaceSm,
        children: [
          _buildModeChip(GameMode.classic),
          _buildModeChip(GameMode.multiplayer),
          _buildModeChip(GameMode.nbaGrid),
        ],
      ),
    ).animate().fadeIn(delay: const Duration(milliseconds: 450));
  }

  Widget _buildModeChip(GameMode mode) {
    final isSelected = _selectedMode == mode;
    final fg = isSelected ? AppColors.voidBlack : AppColors.textSecondary;
    return GestureDetector(
      onTap: () {
        setState(() {
          _selectedMode = mode;
          if (mode != GameMode.multiplayer) {
            _maxPlayers = 2;
          }
          // Tapping NBA Grid auto-switches sport to NBA (the only supported sport for grid).
          if (mode == GameMode.nbaGrid && _selectedSport != SportType.nba) {
            _selectedSport = SportType.nba;
            ref.read(gameStateProvider.notifier).setSport(SportType.nba);
          }
        });
        ref.read(gameStateProvider.notifier).setMode(mode);
      },
      child: AnimatedContainer(
        duration: AppTheme.fastDuration,
        padding: const EdgeInsets.symmetric(
          horizontal: AppTheme.spaceMd,
          vertical: AppTheme.spaceSm,
        ),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary : Colors.transparent,
          borderRadius: BorderRadius.circular(AppTheme.radiusFull),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (mode == GameMode.nbaGrid) ...[
                  Icon(Icons.grid_3x3, size: 14, color: fg),
                  const SizedBox(width: 4),
                ],
                Text(
                  mode.displayName,
                  style: AppTheme.captionStyle.copyWith(
                    color: fg,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                  ),
                ),
              ],
            ),
            Text(
              mode.playerCountLabel,
              style: TextStyle(
                fontSize: 10,
                color: fg.withValues(alpha: 0.7),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCreateCard() {
    final isMultiplayer = _selectedMode == GameMode.multiplayer;
    final isGrid = _selectedMode == GameMode.nbaGrid;
    final IconData modeIcon;
    final String createDescription;
    if (isGrid) {
      modeIcon = Icons.grid_3x3;
      createDescription = 'Start an NBA tic-tac-toe game';
    } else if (isMultiplayer) {
      modeIcon = Icons.groups;
      createDescription = 'Start a party game with friends';
    } else {
      modeIcon = Icons.add_circle_outline;
      createDescription = 'Start a 1v1 game and invite a friend';
    }
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceLg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(AppTheme.spaceSm),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(AppTheme.radiusMd),
                ),
                child: Icon(modeIcon, color: AppColors.primary),
              ),
              const SizedBox(width: AppTheme.spaceMd),
              Text(
                'CREATE GAME',
                style: AppTheme.h3Style.copyWith(fontSize: 18),
              ),
            ],
          ),
          const SizedBox(height: AppTheme.spaceMd),
          Text(createDescription, style: AppTheme.captionStyle),
          // Max players slider for multiplayer
          if (isMultiplayer) ...[
            const SizedBox(height: AppTheme.spaceMd),
            Row(
              children: [
                Text(
                  'Max players: $_maxPlayers',
                  style: AppTheme.captionStyle.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Expanded(
                  child: Slider(
                    value: _maxPlayers.toDouble(),
                    min: 2,
                    max: 10,
                    divisions: 8,
                    activeColor: AppColors.primary,
                    inactiveColor: AppColors.gray700,
                    onChanged: (value) {
                      setState(() => _maxPlayers = value.round());
                    },
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: AppTheme.spaceLg),
          ElevatedButton(
            onPressed: _isCreating ? null : _createRoom,
            child: _isCreating
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: AppColors.voidBlack,
                    ),
                  )
                : const Text('CREATE'),
          ),
        ],
      ),
    ).animate().fadeIn(delay: const Duration(milliseconds: 500));
  }

  Widget _buildJoinCard() {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceLg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        border: Border.all(color: AppColors.gray700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(AppTheme.spaceSm),
                decoration: BoxDecoration(
                  color: AppColors.gray700.withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(AppTheme.radiusMd),
                ),
                child: const Icon(
                  Icons.login,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(width: AppTheme.spaceMd),
              Text(
                'JOIN GAME',
                style: AppTheme.h3Style.copyWith(fontSize: 18),
              ),
            ],
          ),
          const SizedBox(height: AppTheme.spaceMd),
          TextField(
            controller: _roomCodeController,
            textCapitalization: TextCapitalization.characters,
            textAlign: TextAlign.center,
            maxLength: 4,
            style: AppTheme.codeStyle.copyWith(fontSize: 18),
            decoration: InputDecoration(
              hintText: 'XXXX',
              hintStyle: AppTheme.codeStyle.copyWith(
                color: AppColors.textSecondary.withValues(alpha: 0.5),
                fontSize: 18,
              ),
              counterText: '',
              contentPadding: const EdgeInsets.symmetric(
                horizontal: AppTheme.spaceMd,
                vertical: AppTheme.spaceSm,
              ),
            ),
          ),
          const SizedBox(height: AppTheme.spaceMd),
          OutlinedButton(
            onPressed: _isJoining ? null : _joinRoom,
            child: _isJoining
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: AppColors.primary,
                    ),
                  )
                : const Text('JOIN'),
          ),
        ],
      ),
    ).animate().fadeIn(delay: const Duration(milliseconds: 600));
  }
}
