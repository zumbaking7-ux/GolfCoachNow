package com.golfcoachnow.app.ui.components

import android.widget.VideoView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView

/**
 * Plays one clip and then gets out of the way.
 *
 * [onFinished] fires exactly once per outcome the player can reach: the clip
 * ending, the clip failing, or the golfer skipping it. Callers can therefore
 * treat it as "the video step is over" without caring which of those happened,
 * which is what keeps the pipeline moving when an asset is missing or the
 * network is poor.
 */
@Composable
fun VideoPlayer(
    url: String,
    onFinished: () -> Unit,
    modifier: Modifier = Modifier,
) {
    // The listeners below are attached once, when the view is created, so
    // without this they would hold whichever lambda existed at that moment.
    val finish by rememberUpdatedState(onFinished)

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Color.Black),
    ) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { context ->
                VideoView(context).apply {
                    setOnCompletionListener { finish() }
                    setOnErrorListener { _, _, _ ->
                        finish()
                        true // handled, so the system error dialog stays away
                    }
                    setVideoPath(url)
                    start()
                }
            },
        )

        // Deliberately always present, including while the clip is still
        // buffering. A slow connection should cost the golfer a tap, not the rep.
        TextButton(
            onClick = { finish() },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                // The clip fills the screen deliberately, so the player keeps
                // drawing behind the bars. Skip must not: on a gesture phone
                // it would sit under the navigation bar and be hard to hit.
                .navigationBarsPadding()
                .padding(24.dp),
        ) {
            Text(text = "SKIP", color = Color.White, fontSize = 14.sp)
        }
    }
}
