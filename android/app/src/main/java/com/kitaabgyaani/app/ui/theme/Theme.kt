package com.kitaabgyaani.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val DarkBackground = Color(0xFF171512)
val DarkSurface = Color(0xFF211E1A)
val DarkSurfaceRaised = Color(0xFF2A2621)
val DarkSurfaceCard = Color(0xFF302B25)
val DarkSurfaceField = Color(0xFF24211D)
val DarkSurfacePressed = Color(0xFF3A342C)
val DarkOutline = Color(0xFF4C443A)
val DarkOutlineSoft = Color(0xFF383229)

val PrimaryIndigo = Color(0xFFC6A96A)
val PrimarySoft = Color(0xFF3E3525)
val SecondaryCyan = Color(0xFF8FB8AA)
val AccentEmerald = Color(0xFF8EBE91)
val AccentWarning = Color(0xFFD8B56D)
val AccentError = Color(0xFFE08A7D)
val AccentInfo = Color(0xFF8FAFC6)
val TextLight = Color(0xFFF2EDE3)
val TextMuted = Color(0xFFB7AC9C)
val TextSubtle = Color(0xFF8F8374)

private val DarkColorScheme = darkColorScheme(
    primary = PrimaryIndigo,
    onPrimary = Color(0xFF2D2516),
    primaryContainer = PrimarySoft,
    onPrimaryContainer = Color(0xFFEADAB3),
    secondary = SecondaryCyan,
    onSecondary = Color(0xFF182722),
    secondaryContainer = Color(0xFF263C35),
    onSecondaryContainer = Color(0xFFCDE3DA),
    tertiary = AccentInfo,
    onTertiary = Color(0xFF172532),
    tertiaryContainer = Color(0xFF263847),
    onTertiaryContainer = Color(0xFFD1E4F1),
    background = DarkBackground,
    surface = DarkSurface,
    surfaceVariant = DarkSurfaceCard,
    error = AccentError,
    onError = Color(0xFF331613),
    errorContainer = Color(0xFF4B2520),
    onErrorContainer = Color(0xFFFFD6D0),
    outline = DarkOutline,
    outlineVariant = DarkOutlineSoft,
    inverseSurface = Color(0xFFE8DECF),
    inverseOnSurface = Color(0xFF2B2721),
    scrim = Color(0xCC0D0C0A),
    onBackground = TextLight,
    onSurface = TextLight,
    onSurfaceVariant = TextMuted
)

private val LightColorScheme = lightColorScheme(
    primary = PrimaryIndigo,
    secondary = SecondaryCyan,
    background = Color.White,
    surface = Color(0xFFF1F5F9),
    onPrimary = Color.White,
    onSecondary = Color.White,
    onBackground = Color(0xFF0F172A),
    onSurface = Color(0xFF0F172A)
)

val Typography = androidx.compose.material3.Typography(
    bodyLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 25.sp,
        letterSpacing = 0.sp
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 22.sp,
        letterSpacing = 0.sp
    ),
    labelMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        letterSpacing = 0.sp
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 22.sp,
        lineHeight = 28.sp,
        letterSpacing = 0.sp
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 18.sp,
        lineHeight = 24.sp,
        letterSpacing = 0.sp
    )
)

@Composable
fun KitaabGyaaniTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
