package com.golfcoachnow.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.data.model.GolfModule
import com.golfcoachnow.app.ui.components.VideoPlayer
import com.golfcoachnow.app.ui.theme.GolfGreen

/**
 * The instructional clip that plays between tapping an engine and the camera
 * opening.
 *
 * The rule this screen is built around: it always hands off to the camera. It
 * does that when the clip finishes, when the clip fails, when there is no clip
 * published yet, and whenever the golfer decides they have seen enough. No path
 * through here leaves somebody looking at a black rectangle, because that is the
 * one failure that would make the pipeline feel broken rather than unfinished.
 */
@Composable
fun InstructionalVideoScreen(
    module: GolfModule,
    onFinished: () -> Unit,
    onUnavailable: () -> Unit = onFinished,
) {
    var url by remember { mutableStateOf<String?>(null) }
    var resolved by remember { mutableStateOf(false) }

    LaunchedEffect(module) {
        // A failed request is treated exactly like an unpublished video. The
        // golfer came here to record, and a coaching clip is not worth blocking
        // that on.
        url = ApiClient.getInstructionalVideo(module)
            .getOrNull()
            ?.url
            ?.takeIf { it.isNotBlank() }
        resolved = true
    }

    LaunchedEffect(resolved, url) {
        // Ahead of the camera an unpublished clip is skipped silently. Reached
        // on its own from Swing Learn it has to be reported, or the button
        // appears to do nothing at all.
        if (resolved && url == null) onUnavailable()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black),
        contentAlignment = Alignment.Center,
    ) {
        val videoUrl = url
        if (videoUrl != null) {
            VideoPlayer(url = videoUrl, onFinished = onFinished)
        } else if (!resolved) {
            CircularProgressIndicator(color = GolfGreen)
        }
    }
}
