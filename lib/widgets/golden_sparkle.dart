import 'dart:math' show Random, pi, cos, sin;
import 'package:flutter/material.dart';

/// Golden Sparkle Particle Background
/// Floating golden particles that create a premium treasure-hunting atmosphere.
/// Usage: Wrap any screen with GoldenSparkleBackground(child: YourScreen())
class GoldenSparkleBackground extends StatefulWidget {
  final Widget child;
  final SparkleIntensity intensity;

  const GoldenSparkleBackground({
    super.key,
    required this.child,
    this.intensity = SparkleIntensity.medium,
  });

  @override
  State<GoldenSparkleBackground> createState() => _GoldenSparkleBackgroundState();
}

enum SparkleIntensity { low, medium, high }

class _GoldenSparkleBackgroundState extends State<GoldenSparkleBackground>
    with TickerProviderStateMixin {
  late final AnimationController _particleController;
  final List<Particle> _particles = [];
  final Random _random = Random();

  int get particleCount => switch (widget.intensity) {
    SparkleIntensity.low => 20,
    SparkleIntensity.medium => 40,
    SparkleIntensity.high => 60,
  };

  @override
  void initState() {
    super.initState();
    _particleController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 5),
    )..repeat();

    // Initialize particles
    for (int i = 0; i < particleCount; i++) {
      _particles.add(_createParticle());
    }
  }

  Particle _createParticle() {
    return Particle(
      x: _random.nextDouble(),
      y: _random.nextDouble(),
      size: 1.0 + _random.nextDouble() * 2.5,
      opacity: 0.08 + _random.nextDouble() * 0.22,
      speed: 0.15 + _random.nextDouble() * 0.35,
      phase: _random.nextDouble() * pi * 2,
    );
  }

  @override
  void dispose() {
    _particleController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      body: Stack(
        children: [
          // Base dark gradient
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0xFF0A0A0F),
                  Color(0xFF0D0818),
                  Color(0xFF0A0A0F),
                ],
              ),
            ),
          ),
          // Animated particles
          AnimatedBuilder(
            animation: _particleController,
            builder: (context, child) {
              return CustomPaint(
                size: Size.infinite,
                painter: ParticlePainter(
                  particles: _particles,
                  progress: _particleController.value,
                  intensity: widget.intensity,
                ),
              );
            },
          ),
          // Screen content
          widget.child,
        ],
      ),
    );
  }
}

class Particle {
  double x; // 0-1 normalized
  double y; // 0-1 normalized
  final double size;
  final double opacity;
  final double speed;
  final double phase;

  Particle({
    required this.x,
    required this.y,
    required this.size,
    required this.opacity,
    required this.speed,
    required this.phase,
  });
}

class ParticlePainter extends CustomPainter {
  final List<Particle> particles;
  final double progress;
  final SparkleIntensity intensity;

  ParticlePainter({
    required this.particles,
    required this.progress,
    required this.intensity,
  });

  @override
  void paint(Canvas canvas, Size size) {
    for (final particle in particles) {
      // Drift upward
      final driftY = particle.y - (progress * particle.speed) % 1.0;
      final adjustedY = driftY < 0 ? 1.0 + driftY : driftY;

      // Slight horizontal sway
      final sway = cos(progress * pi * 2 + particle.phase) * 0.02;
      final adjustedX = (particle.x + sway).clamp(0.0, 1.0);

      // Pulsing opacity
      final pulse = 0.5 + 0.5 * cos(progress * pi * 2 * 0.7 + particle.phase);
      final currentOpacity = (particle.opacity * (0.4 + 0.6 * pulse)).clamp(0.05, 0.35);

      final paint = Paint()
        ..color = Color(0x4DFFD700).withOpacity(currentOpacity)
        ..style = PaintingStyle.fill;

      final center = Offset(adjustedX * size.width, adjustedY * size.height);

      // Draw glow halo
      final glowPaint = Paint()
        ..color = Color(0x26FF8F00).withOpacity(currentOpacity * 0.5)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6);

      canvas.drawCircle(center, particle.size * 3, glowPaint);

      // Draw core
      canvas.drawCircle(center, particle.size, paint);

      // Bright center dot for larger particles
      if (particle.size > 2.0) {
        final brightPaint = Paint()
          ..color = const Color(0xFFFFD700).withOpacity(currentOpacity * 1.5)
          ..style = PaintingStyle.fill;
        canvas.drawCircle(center, particle.size * 0.4, brightPaint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant ParticlePainter oldDelegate) => true;
}
