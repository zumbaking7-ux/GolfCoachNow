package com.golfcoachnow.app.ui.screens

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.*
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.golfcoachnow.app.R
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.data.api.ApiException
import com.golfcoachnow.app.data.model.CorrectionResponse
import com.golfcoachnow.app.data.model.GolfModule
import com.golfcoachnow.app.ui.components.VideoPlayer
import com.golfcoachnow.app.ui.theme.*
import com.golfcoachnow.app.util.EntitlementManager
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun CameraScreen(
    module: GolfModule,
    onBack: () -> Unit,
    onPaywall: () -> Unit,
    onSignIn: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var hasPermissions by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        hasPermissions = permissions.values.all { it }
    }

    LaunchedEffect(Unit) {
        if (!hasPermissions) {
            permissionLauncher.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO))
        }
    }

    var isRecording by remember { mutableStateOf(false) }
    var repCount by remember { mutableIntStateOf(0) }
    var statusText by remember { mutableStateOf("Tap record to start") }
    var correction by remember { mutableStateOf<CorrectionResponse?>(null) }

    // Set only while the correction clip is on screen. The written correction
    // sits underneath it the whole time and is what remains once it clears.
    var correctionVideoUrl by remember { mutableStateOf<String?>(null) }
    var activeRecording by remember { mutableStateOf<Recording?>(null) }
    var videoCapture by remember { mutableStateOf<VideoCapture<Recorder>?>(null) }

    val cameraProviderFuture = remember { ProcessCameraProvider.getInstance(context) }

    Box(modifier = Modifier.fillMaxSize().background(DarkBackground)) {
        if (!hasPermissions) {
            Text(
                text = "Camera & microphone permissions required",
                color = Color.White,
                modifier = Modifier.align(Alignment.Center),
            )
        }

        if (hasPermissions) AndroidView(
            factory = { ctx ->
                val previewView = PreviewView(ctx)
                val cameraProvider = cameraProviderFuture.get()
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }

                val recorder = Recorder.Builder()
                    .setQualitySelector(QualitySelector.from(Quality.HD))
                    .build()
                videoCapture = VideoCapture.withOutput(recorder)

                try {
                    cameraProvider.unbindAll()
                    cameraProvider.bindToLifecycle(
                        ctx as androidx.lifecycle.LifecycleOwner,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        videoCapture,
                    )
                } catch (_: Exception) { }

                previewView
            },
            modifier = Modifier.fillMaxSize(),
        )

        // Top bar
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = Color.White)
            }
            Spacer(Modifier.weight(1f))
            Surface(
                shape = RoundedCornerShape(12.dp),
                color = GolfGreen,
                shadowElevation = 4.dp,
            ) {
                Text(
                    text = module.title,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.Black,
                )
            }
            Spacer(Modifier.weight(1f))
            Spacer(Modifier.size(48.dp))
        }

        // Rep counter
        Surface(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .statusBarsPadding()
                .padding(top = 64.dp),
            shape = RoundedCornerShape(10.dp),
            color = DarkCard.copy(alpha = 0.85f),
            border = ButtonDefaults.outlinedButtonBorder.copy(
                brush = Brush.linearGradient(listOf(GolfGreenBorder, GolfGreenBorder))
            ),
        ) {
            Text(
                text = "Rep: $repCount",
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
            )
        }

        // Status text
        if (statusText.isNotEmpty() && correction == null) {
            Surface(
                modifier = Modifier.align(Alignment.Center),
                shape = RoundedCornerShape(10.dp),
                color = DarkCard.copy(alpha = 0.8f),
            ) {
                Text(
                    text = statusText,
                    fontSize = 16.sp,
                    color = Color.White.copy(alpha = 0.8f),
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                )
            }
        }

        // Correction card
        correction?.let { resp ->
            Column(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 140.dp)
                    .padding(horizontal = 16.dp)
                    .shadow(8.dp, RoundedCornerShape(14.dp), ambientColor = GolfGreen.copy(alpha = 0.3f), spotColor = GolfGreen.copy(alpha = 0.3f))
                    .clip(RoundedCornerShape(14.dp))
                    .border(1.dp, GolfGreenBorder, RoundedCornerShape(14.dp))
                    .background(DarkCard.copy(alpha = 0.95f))
                    .padding(16.dp),
            ) {
                Text(
                    text = resp.dominantFault.uppercase().replace("_", " "),
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = GolfGreen,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    text = resp.correction,
                    fontSize = 15.sp,
                    color = Color.White,
                )
                Spacer(Modifier.height(10.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    Row(
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .border(1.dp, GolfGreenBorder, RoundedCornerShape(8.dp))
                            .background(DarkCard)
                            .clickable { shareCorrection(context, module, resp.dominantFault, resp.correction) }
                            .padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Image(
                            painter = painterResource(id = R.drawable.ic_share_plane),
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                            contentScale = ContentScale.Fit,
                        )
                        Spacer(Modifier.width(6.dp))
                        Text("Share", color = GolfGreen, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        // Bottom controls
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .align(Alignment.BottomCenter)
                .navigationBarsPadding()
                .padding(bottom = 32.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Spacer(Modifier.size(56.dp))

            // Record button
            IconButton(
                onClick = {
                    if (isRecording) {
                        activeRecording?.stop()
                        activeRecording = null
                        isRecording = false
                    } else {
                        correction = null
                        correctionVideoUrl = null
                        statusText = "Recording..."
                        isRecording = true

                        // Counted on a completed analysis, not on pressing
                        // record. Showing "Rep: 1" for an attempt that came
                        // back with nothing tells the golfer they used one
                        // when they did not - and the server only charges an
                        // allowance once there is coaching to show.
                        val file = File(context.cacheDir, "golf_rep_${repCount + 1}.mp4")
                        val outputOptions = FileOutputOptions.Builder(file).build()

                        val vc = videoCapture ?: return@IconButton
                        try {
                            activeRecording = vc.output
                                .prepareRecording(context, outputOptions)
                                .withAudioEnabled()
                                .start(ContextCompat.getMainExecutor(context)) { event ->
                                    if (event is VideoRecordEvent.Finalize) {
                                        if (event.hasError()) {
                                            statusText = "Recording failed"
                                            isRecording = false
                                        } else {
                                            statusText = "Uploading & analyzing..."
                                            isRecording = false
                                            scope.launch {
                                                val result = ApiClient.uploadVideo(
                                                    file = file,
                                                    module = module,
                                                    deviceId = EntitlementManager.deviceId,
                                                )
                                                result.onSuccess { resp ->
                                                    if (resp.status != "no_swing_detected") repCount++
                                                    correction = resp
                                                    correctionVideoUrl =
                                                        resp.correctionVideoUrl?.takeIf { it.isNotBlank() }
                                                    statusText = ""
                                                    ApiClient.trackEvent("rep_completed", module)
                                                }.onFailure { err ->
                                                    if (err is ApiException && err.code == 401) {
                                                        statusText = "Sign in to keep analysing your swing."
                                                        onSignIn()
                                                    } else if (err is ApiException && err.code == 403) {
                                                        onPaywall()
                                                    } else {
                                                        statusText = err.message ?: "Analysis failed"
                                                    }
                                                }
                                                file.delete()
                                            }
                                        }
                                    }
                                }
                        } catch (_: SecurityException) {
                            statusText = "Camera permission required"
                            isRecording = false
                        }
                    }
                },
                modifier = Modifier
                    .size(72.dp)
                    .shadow(if (isRecording) 0.dp else 8.dp, CircleShape, ambientColor = GolfGreen.copy(alpha = 0.4f), spotColor = GolfGreen.copy(alpha = 0.4f))
                    .border(3.dp, if (isRecording) Color.Red else GolfGreen, CircleShape),
            ) {
                if (isRecording) {
                    Icon(
                        Icons.Default.Stop,
                        "Stop",
                        tint = Color.Red,
                        modifier = Modifier.size(36.dp),
                    )
                } else {
                    Box(
                        modifier = Modifier
                            .size(56.dp)
                            .background(Color.Red, CircleShape)
                    )
                }
            }

            Spacer(Modifier.size(56.dp))
        }

        // Wire four. Declared last so it covers the camera and the correction
        // card while it plays; clearing the url reveals the written correction
        // that was already sitting underneath.
        correctionVideoUrl?.let { videoUrl ->
            VideoPlayer(
                url = videoUrl,
                onFinished = { correctionVideoUrl = null },
                modifier = Modifier.matchParentSize(),
            )
        }
    }
}

private fun shareCorrection(context: Context, module: GolfModule, fault: String, correction: String) {
    val text = buildString {
        appendLine("GolfCoachNow — ${module.title} Analysis")
        appendLine()
        appendLine("Fault: ${fault.replace("_", " ").uppercase()}")
        appendLine("Correction: $correction")
        appendLine()
        appendLine("Try GolfCoachNow — AI-powered golf coaching")
    }
    val intent = Intent.createChooser(
        Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
        },
        "Share Correction"
    )
    context.startActivity(intent)
}
