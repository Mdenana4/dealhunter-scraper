import 'package:flutter/material.dart';

class AppTheme {
  // Brand colours
  static const Color primary   = Color(0xFF1E88E5); // Blue
  static const Color genuine   = Color(0xFF43A047); // Green  — verified deal
  static const Color fake      = Color(0xFFE53935); // Red    — fake discount
  static const Color uncertain = Color(0xFFFB8C00); // Orange — uncertain
  static const Color surface   = Color(0xFFF8F9FA);
  static const Color cardBg    = Color(0xFFFFFFFF);

  static const Color primaryDark  = Color(0xFF1565C0);
  static const Color surfaceDark  = Color(0xFF121212);
  static const Color cardBgDark   = Color(0xFF1E1E1E);

  static ThemeData light() {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primary,
        brightness: Brightness.light,
        primary: primary,
        surface: surface,
      ),
    );
    return base.copyWith(
      scaffoldBackgroundColor: surface,
      appBarTheme: const AppBarTheme(
        backgroundColor: primary,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: Colors.white,
          fontSize: 18,
          fontWeight: FontWeight.w600,
          fontFamily: 'Cairo',
        ),
      ),
      cardTheme: CardTheme(
        color: cardBg,
        elevation: 2,
        shadowColor: Colors.black12,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            fontFamily: 'Cairo',
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: primary,
          side: const BorderSide(color: primary),
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFDDE1E7)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFDDE1E7)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: primary, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: fake),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        labelStyle: const TextStyle(fontFamily: 'Cairo'),
        hintStyle: TextStyle(fontFamily: 'Cairo', color: Colors.grey.shade400),
      ),
      textTheme: _textTheme(Brightness.light),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        selectedItemColor: primary,
        unselectedItemColor: Colors.grey,
        showUnselectedLabels: true,
        type: BottomNavigationBarType.fixed,
        elevation: 8,
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        backgroundColor: Colors.grey.shade100,
        selectedColor: primary.withOpacity(0.15),
        labelStyle: const TextStyle(fontSize: 13, fontFamily: 'Cairo'),
      ),
    );
  }

  static ThemeData dark() {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primary,
        brightness: Brightness.dark,
        primary: primary,
        surface: surfaceDark,
      ),
    );
    return base.copyWith(
      scaffoldBackgroundColor: surfaceDark,
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF1A1A2E),
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardTheme(
        color: cardBgDark,
        elevation: 4,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      textTheme: _textTheme(Brightness.dark),
    );
  }

  static TextTheme _textTheme(Brightness brightness) {
    final color = brightness == Brightness.light ? const Color(0xFF1A1A2E) : Colors.white;
    return TextTheme(
      displayLarge:  TextStyle(fontFamily: 'Cairo', fontSize: 32, fontWeight: FontWeight.w700, color: color),
      displayMedium: TextStyle(fontFamily: 'Cairo', fontSize: 28, fontWeight: FontWeight.w700, color: color),
      headlineLarge: TextStyle(fontFamily: 'Cairo', fontSize: 24, fontWeight: FontWeight.w700, color: color),
      headlineMedium:TextStyle(fontFamily: 'Cairo', fontSize: 20, fontWeight: FontWeight.w600, color: color),
      headlineSmall: TextStyle(fontFamily: 'Cairo', fontSize: 18, fontWeight: FontWeight.w600, color: color),
      titleLarge:    TextStyle(fontFamily: 'Cairo', fontSize: 16, fontWeight: FontWeight.w600, color: color),
      titleMedium:   TextStyle(fontFamily: 'Cairo', fontSize: 15, fontWeight: FontWeight.w500, color: color),
      bodyLarge:     TextStyle(fontFamily: 'Cairo', fontSize: 15, color: color),
      bodyMedium:    TextStyle(fontFamily: 'Cairo', fontSize: 14, color: color),
      bodySmall:     TextStyle(fontFamily: 'Cairo', fontSize: 12, color: color.withOpacity(0.7)),
      labelLarge:    TextStyle(fontFamily: 'Cairo', fontSize: 14, fontWeight: FontWeight.w600, color: color),
    );
  }

  // Verification result colours
  static Color verificationColor(String verdict) {
    switch (verdict) {
      case 'genuine': return genuine;
      case 'fake':    return fake;
      default:        return uncertain;
    }
  }

  // Tier badge colours
  static Color tierColor(String tier) {
    switch (tier) {
      case 'vip':     return const Color(0xFF7B1FA2);   // Purple
      case 'premium': return const Color(0xFF1E88E5);   // Blue
      case 'basic':   return const Color(0xFF00897B);   // Teal
      default:        return Colors.grey;
    }
  }
}
