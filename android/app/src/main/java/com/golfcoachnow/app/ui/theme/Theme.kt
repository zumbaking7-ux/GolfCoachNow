package com.golfcoachnow.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val GolfGreen = Color(0xFF34C759)
val DarkBackground = Color(0xFF000000)
val DarkSurface = Color(0xFF1C1C1E)
val DarkCard = Color(0xFF2C2C2E)
val YellowAccent = Color(0xFFFFD60A)

private val DarkColors = darkColorScheme(
    primary = GolfGreen,
    onPrimary = Color.White,
    secondary = YellowAccent,
    background = DarkBackground,
    surface = DarkSurface,
    surfaceVariant = DarkCard,
    onBackground = Color.White,
    onSurface = Color.White,
    onSurfaceVariant = Color(0xFF8E8E93),
    error = Color(0xFFFF3B30),
)

@Composable
fun GolfCoachNowTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColors,
        content = content,
    )
}
