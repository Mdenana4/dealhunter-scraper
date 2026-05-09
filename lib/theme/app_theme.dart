/// ============================================================================
/// DealHunter Egypt — Complete ThemeData
/// ============================================================================
/// Dark mode default with McDonald's-inspired color psychology.
/// Every text style, shape, and shadow is designed to trigger "DEAL HUNGER."
/// ============================================================================

import 'package:flutter/material.dart';
import 'app_colors.dart';

class AppTheme {
  AppTheme._();

  /// Primary font family — Inter for English, Cairo for Arabic
  static const String fontFamily = 'Inter';
  static const String fontFamilyArabic = 'Cairo';

  // ═══════════════════════════════════════════════════════════════════════════
  // DARK THEME (Default)
  // ═══════════════════════════════════════════════════════════════════════════
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.darkBackground,
      canvasColor: AppColors.darkCard,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.electricOrange,
        onPrimary: Colors.white,
        secondary: AppColors.deepPurple,
        onSecondary: Colors.white,
        surface: AppColors.darkCard,
        onSurface: AppColors.textPrimary,
        error: AppColors.crimsonRed,
        onError: Colors.white,
        background: AppColors.darkBackground,
        onBackground: AppColors.textPrimary,
        tertiary: AppColors.emeraldGreen,
      ),

      // ── Typography ─────────────────────────────────────────────────────
      textTheme: _textTheme,

      // ── App Bar ────────────────────────────────────────────────────────
      appBarTheme: _appBarTheme,

      // ── Bottom Nav ─────────────────────────────────────────────────────
      bottomNavigationBarTheme: _bottomNavTheme,

      // ── Cards ──────────────────────────────────────────────────────────
      cardTheme: _cardTheme,

      // ── Buttons ────────────────────────────────────────────────────────
      elevatedButtonTheme: _elevatedButtonTheme,
      outlinedButtonTheme: _outlinedButtonTheme,
      textButtonTheme: _textButtonTheme,

      // ── Input ──────────────────────────────────────────────────────────
      inputDecorationTheme: _inputDecorationTheme,

      // ── Chips ──────────────────────────────────────────────────────────
      chipTheme: _chipTheme,

      // ── Shapes ─────────────────────────────────────────────────────────
      shapeTheme: const ShapeThemeData(
        // Default border radius for all components
      ),

      // ── Divider ────────────────────────────────────────────────────────
      dividerTheme: DividerThemeData(
        color: AppColors.textMuted.withOpacity(0.3),
        thickness: 0.5,
      ),

      // ── Progress ───────────────────────────────────────────────────────
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.electricOrange,
        linearTrackColor: AppColors.darkSurface,
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // TEXT THEME — Emotional typography hierarchy
  // ═══════════════════════════════════════════════════════════════════════════
  static TextTheme get _textTheme {
    const baseTextStyle = TextStyle(
      fontFamily: fontFamily,
      color: AppColors.textPrimary,
      letterSpacing: -0.3,
    );

    return TextTheme(
      // Display — Massive headlines (hero sections)
      displayLarge: baseTextStyle.copyWith(
        fontSize: 48,
        fontWeight: FontWeight.w800,
        letterSpacing: -1.5,
        height: 1.1,
      ),
      displayMedium: baseTextStyle.copyWith(
        fontSize: 36,
        fontWeight: FontWeight.w700,
        letterSpacing: -1,
        height: 1.15,
      ),

      // Headlines — Deal titles, page headers
      headlineLarge: baseTextStyle.copyWith(
        fontSize: 28,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.8,
        height: 1.2,
      ),
      headlineMedium: baseTextStyle.copyWith(
        fontSize: 22,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.5,
        height: 1.25,
      ),
      headlineSmall: baseTextStyle.copyWith(
        fontSize: 18,
        fontWeight: FontWeight.w600,
        height: 1.3,
      ),

      // Titles — Section headers, card titles
      titleLarge: baseTextStyle.copyWith(
        fontSize: 18,
        fontWeight: FontWeight.w600,
        height: 1.3,
      ),
      titleMedium: baseTextStyle.copyWith(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        height: 1.35,
      ),
      titleSmall: baseTextStyle.copyWith(
        fontSize: 14,
        fontWeight: FontWeight.w500,
        color: AppColors.textSecondary,
        height: 1.4,
      ),

      // Body — Descriptions, general text
      bodyLarge: baseTextStyle.copyWith(
        fontSize: 16,
        fontWeight: FontWeight.w400,
        height: 1.5,
      ),
      bodyMedium: baseTextStyle.copyWith(
        fontSize: 14,
        fontWeight: FontWeight.w400,
        height: 1.5,
      ),
      bodySmall: baseTextStyle.copyWith(
        fontSize: 12,
        fontWeight: FontWeight.w400,
        color: AppColors.textSecondary,
        height: 1.45,
      ),

      // Labels — Buttons, chips, small UI
      labelLarge: baseTextStyle.copyWith(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.5,
      ),
      labelMedium: baseTextStyle.copyWith(
        fontSize: 12,
        fontWeight: FontWeight.w500,
        letterSpacing: 0.4,
      ),
      labelSmall: baseTextStyle.copyWith(
        fontSize: 11,
        fontWeight: FontWeight.w500,
        color: AppColors.textMuted,
        letterSpacing: 0.5,
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // APP BAR — Transparent with blur
  // ═══════════════════════════════════════════════════════════════════════════
  static AppBarTheme get _appBarTheme {
    return const AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        fontFamily: fontFamily,
        fontSize: 22,
        fontWeight: FontWeight.w700,
        color: AppColors.textPrimary,
      ),
      iconTheme: IconThemeData(color: AppColors.textSecondary),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // BOTTOM NAV — Dark charcoal with blur
  // ═══════════════════════════════════════════════════════════════════════════
  static BottomNavigationBarThemeData get _bottomNavTheme {
    return BottomNavigationBarThemeData(
      backgroundColor: AppColors.charcoal.withOpacity(0.95),
      elevation: 0,
      type: BottomNavigationBarType.fixed,
      selectedItemColor: AppColors.electricOrange,
      unselectedItemColor: AppColors.textSecondary,
      selectedLabelStyle: const TextStyle(
        fontFamily: fontFamily,
        fontSize: 11,
        fontWeight: FontWeight.w600,
      ),
      unselectedLabelStyle: const TextStyle(
        fontFamily: fontFamily,
        fontSize: 11,
        fontWeight: FontWeight.w400,
      ),
      showSelectedLabels: true,
      showUnselectedLabels: true,
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // CARDS — Glassmorphism-ready
  // ═══════════════════════════════════════════════════════════════════════════
  static CardTheme get _cardTheme {
    return CardTheme(
      color: AppColors.darkCard,
      elevation: 8,
      shadowColor: AppColors.deepPurple.withOpacity(0.2),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(
          color: AppColors.glassBorder,
          width: 0.5,
        ),
      ),
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // BUTTONS — Buy Now style
  // ═══════════════════════════════════════════════════════════════════════════
  static ElevatedButtonThemeData get _elevatedButtonTheme {
    return ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.electricOrange,
        foregroundColor: Colors.white,
        textStyle: const TextStyle(
          fontFamily: fontFamily,
          fontSize: 14,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.5,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        elevation: 4,
        shadowColor: AppColors.electricOrange.withOpacity(0.4),
      ).copyWith(
        overlayColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.pressed)) {
            return Colors.white.withOpacity(0.2);
          }
          return null;
        }),
      ),
    );
  }

  static OutlinedButtonThemeData get _outlinedButtonTheme {
    return OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.electricOrange,
        side: const BorderSide(color: AppColors.electricOrange, width: 1.5),
        textStyle: const TextStyle(
          fontFamily: fontFamily,
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
    );
  }

  static TextButtonThemeData get _textButtonTheme {
    return TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: AppColors.goldenYellow,
        textStyle: const TextStyle(
          fontFamily: fontFamily,
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // INPUT — Search bar, filters
  // ═══════════════════════════════════════════════════════════════════════════
  static InputDecorationTheme get _inputDecorationTheme {
    return InputDecorationTheme(
      filled: true,
      fillColor: AppColors.darkSurface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      hintStyle: TextStyle(
        fontFamily: fontFamily,
        fontSize: 15,
        color: AppColors.textMuted,
        fontWeight: FontWeight.w400,
      ),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(28),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(28),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(28),
        borderSide: const BorderSide(color: AppColors.electricOrange, width: 2),
      ),
      prefixIconColor: AppColors.textMuted,
      suffixIconColor: AppColors.textSecondary,
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // CHIPS — Category filters, source filters
  // ═══════════════════════════════════════════════════════════════════════════
  static ChipThemeData get _chipTheme {
    return ChipThemeData(
      backgroundColor: AppColors.darkSurface,
      selectedColor: AppColors.electricOrange,
      secondarySelectedColor: AppColors.deepPurple,
      labelStyle: const TextStyle(
        fontFamily: fontFamily,
        fontSize: 13,
        fontWeight: FontWeight.w500,
        color: AppColors.textSecondary,
      ),
      secondaryLabelStyle: const TextStyle(
        fontFamily: fontFamily,
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: Colors.white,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
        side: BorderSide(color: AppColors.glassBorder, width: 0.5),
      ),
      elevation: 2,
      shadowColor: Colors.black.withOpacity(0.3),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // LIGHT THEME (Optional toggle)
  // ═══════════════════════════════════════════════════════════════════════════
  static ThemeData get lightTheme {
    return darkTheme.copyWith(
      brightness: Brightness.light,
      scaffoldBackgroundColor: const Color(0xFFF5F5FA),
      canvasColor: Colors.white,
      cardTheme: CardTheme(
        color: Colors.white,
        elevation: 4,
        shadowColor: Colors.black.withOpacity(0.08),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
      ),
      colorScheme: const ColorScheme.light(
        primary: AppColors.electricOrange,
        surface: Colors.white,
        onSurface: Color(0xFF1A1A2E),
        background: Color(0xFFF5F5FA),
      ),
      textTheme: _textTheme.apply(
        bodyColor: const Color(0xFF1A1A2E),
        displayColor: const Color(0xFF1A1A2E),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // GLASSMORPHISM DECORATION — Reusable for any widget
  // ═══════════════════════════════════════════════════════════════════════════
  static BoxDecoration glassmorphism({
    Color? borderColor,
    double? blurOpacity,
  }) {
    return BoxDecoration(
      color: AppColors.darkCard.withOpacity(blurOpacity ?? 0.7),
      borderRadius: BorderRadius.circular(20),
      border: Border.all(
        color: borderColor ?? AppColors.glassBorder,
        width: 0.8,
      ),
      boxShadow: [
        BoxShadow(
          color: AppColors.deepPurple.withOpacity(0.1),
          blurRadius: 20,
          spreadRadius: -5,
          offset: const Offset(0, 8),
        ),
      ],
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // GLOW EFFECT — For discount badges, CTAs
  // ═══════════════════════════════════════════════════════════════════════════
  static List<BoxShadow> glow(Color color, {double intensity = 0.5}) {
    return [
      BoxShadow(
        color: color.withOpacity(intensity * 0.6),
        blurRadius: 12,
        spreadRadius: -2,
      ),
      BoxShadow(
        color: color.withOpacity(intensity * 0.3),
        blurRadius: 30,
        spreadRadius: -8,
      ),
    ];
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // TEXT STYLE HELPER — Matches profile_screen usage
  // ═══════════════════════════════════════════════════════════════════════════
  static TextStyle textStyle({
    double fontSize = 14,
    FontWeight fontWeight = FontWeight.w400,
    Color color = Colors.white,
    double? letterSpacing,
    double? height,
    TextDecoration decoration = TextDecoration.none,
  }) {
    return TextStyle(
      fontFamily: fontFamily,
      fontSize: fontSize,
      fontWeight: fontWeight,
      color: color,
      letterSpacing: letterSpacing,
      height: height,
      decoration: decoration,
    );
  }
}
