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
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.data.api.ApiException
import com.golfcoachnow.app.data.model.CorrectionResponse
import com.golfcoachnow.app.data.model.GolfModule
import com.golfcoachnow.app.ui.theme.GolfGreen
import com.golfcoachnow.app.ui.theme.YellowAccent
import com.golfcoachnow.app.util.EntitlementManager
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun CameraScreen(
    module: GolfModule,
    onBack: () -> Unit,
    onPaywall: () -> Unit,
    onTalkMode: () -> Unit,
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
    var activeRecording by remember { mutableStateOf<Recording?>(null) }
    var videoCapture by remember { mutableStateOf<VideoCapture<Recorder>?>(null) }

    val cameraProviderFuture = remember { ProcessCameraProvider.getInstance(context) }

    Box(modifier = Modifier.fillMaxSize().background(Color.Black)) {
        if (!hasPermissions) {
            Text(
                text = "Camera & microphone permissions required",
                color = Color.White,
                modifier = Modifier.align(Alignment.Center),
            )
        }

        // Camera preview
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
            ) {
                Text(
                    text = module.title,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                )
            }
            Spacer(Modifier.weight(1f))
            Spacer(Modifier.size(48.dp))
        }

        // Rep counter
        Text(
            text = "Rep: $repCount",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            modifier = Modifier
                .align(Alignment.TopCenter)
                .statusBarsPadding()
                .padding(top = 64.dp),
        )

        // Status text
        if (statusText.isNotEmpty() && correction == null) {
            Text(
                text = statusText,
                fontSize = 16.sp,
                color = Color.White.copy(alpha = 0.7f),
                modifier = Modifier.align(Alignment.Center),
            )
        }

        // Correction card
        correction?.let { resp ->
            Column(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 140.dp)
                    .padding(horizontal = 16.dp)
                    .background(Color.Black.copy(alpha = 0.85f), RoundedCornerShape(16.dp))
                    .padding(16.dp),
            ) {
                Text(
                    text = resp.dominantFault.uppercase().replace("_", " "),
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = YellowAccent,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    text = resp.correction,
                    fontSize = 15.sp,
                    color = Color.White,
                )
                Spacer(Modifier.height(8.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = {
                        shareCorrection(context, module, resp.dominantFault, resp.correction)
                    }) {
                        Icon(Icons.Default.Share, null, tint = GolfGreen, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Share", color = GolfGreen)
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
            // Talk button
            IconButton(
                onClick = onTalkMode,
                modifier = Modifier
                    .size(56.dp)
                    .background(GolfGreen, CircleShape),
            ) {
                Icon(Icons.Default.GraphicEq, "Talk Mode", tint = Color.White)
            }

            // Record button
            IconButton(
                onClick = {
                    if (isRecording) {
                        activeRecording?.stop()
                        activeRecording = null
                        isRecording = false
                    } else {
                        correction = null
                        statusText = "Recording..."
                        isRecording = true
                        repCount++

                        val file = File(context.cacheDir, "golf_rep_$repCount.mp4")
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
                                                    correction = resp
                                                    statusText = ""
                                                }.onFailure { err ->
                                                    if (err is ApiException && err.code == 403) {
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
                    .border(4.dp, Color.White, CircleShape),
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

            // Flip camera placeholder
            Spacer(Modifier.size(56.dp))
        }
    }
}

private fun shareCorrection(context: Context, module: GolfModule, fault: String, correction: String) {
    val text = buildString {
        appendLine("GolfCoachNow — ${module.title} Analysis")
        appendLine()
        appendLine("Fault: ${fault.replace("_", " ").uppercase()}")
        appendLine("Correction: $correction")
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
