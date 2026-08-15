package com.golfcoachnow.app.ui.screens

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.golfcoachnow.app.R
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.data.model.GolfModule
import com.golfcoachnow.app.data.model.TalkResponse
import com.golfcoachnow.app.ui.theme.*
import com.golfcoachnow.app.util.EntitlementManager
import kotlinx.coroutines.launch
import java.util.Locale

@Composable
fun TalkModeScreen(
    module: GolfModule,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var hasMicPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        )
    }
    val micPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> hasMicPermission = granted }

    LaunchedEffect(Unit) {
        if (!hasMicPermission) micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
    }

    var isListening by remember { mutableStateOf(false) }
    var transcript by remember { mutableStateOf("") }
    var correction by remember { mutableStateOf<TalkResponse?>(null) }
    var statusText by remember { mutableStateOf("Tap the mic and describe your swing") }

    val tts = remember {
        var engine: TextToSpeech? = null
        engine = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                engine?.language = Locale.US
            }
        }
        engine
    }

    val speechRecognizer = remember { SpeechRecognizer.createSpeechRecognizer(context) }

    DisposableEffect(Unit) {
        onDispose {
            speechRecognizer.destroy()
            tts?.shutdown()
        }
    }

    val pulseAnim = rememberInfiniteTransition(label = "pulse")
    val pulseScale by pulseAnim.animateFloat(
        initialValue = 1f,
        targetValue = 1.2f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulseScale",
    )

    fun startListening() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            statusText = "Microphone permission required"
            return
        }

        correction = null
        transcript = ""
        isListening = true
        statusText = "Listening..."

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }

        speechRecognizer.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val text = matches?.firstOrNull() ?: ""
                transcript = text
                isListening = false

                if (text.isNotBlank()) {
                    statusText = "Analyzing..."
                    scope.launch {
                        val result = ApiClient.sendTalkRequest(
                            text = text,
                            module = module,
                            deviceId = EntitlementManager.deviceId,
                        )
                        result.onSuccess { resp ->
                            correction = resp
                            statusText = ""
                            if (resp.matched) {
                                tts?.speak(resp.correction, TextToSpeech.QUEUE_FLUSH, null, "correction")
                            }
                        }.onFailure {
                            statusText = "Failed to get correction"
                        }
                    }
                } else {
                    statusText = "Didn't catch that. Try again."
                }
            }

            override fun onPartialResults(partialResults: Bundle?) {
                val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                transcript = matches?.firstOrNull() ?: transcript
            }

            override fun onError(error: Int) {
                isListening = false
                statusText = "Try again"
            }

            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        speechRecognizer.startListening(intent)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .statusBarsPadding()
            .navigationBarsPadding(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // Top bar
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = Color.White)
            }
            Spacer(Modifier.weight(1f))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Image(
                    painter = painterResource(id = R.drawable.ic_talk_mode),
                    contentDescription = null,
                    modifier = Modifier.size(24.dp),
                    contentScale = ContentScale.Fit,
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    text = "TALK MODE",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.ExtraBold,
                    color = GolfGreen,
                    letterSpacing = 1.sp,
                )
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
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.Black,
                )
            }
        }

        Spacer(Modifier.height(24.dp))

        // Pulse icon
        Image(
            painter = painterResource(id = R.drawable.ic_pulse),
            contentDescription = null,
            modifier = Modifier.size(48.dp),
            contentScale = ContentScale.Fit,
        )

        Spacer(Modifier.height(16.dp))

        // Status
        Text(
            text = statusText,
            fontSize = 16.sp,
            color = TextMuted,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 32.dp),
        )

        // Transcript
        if (transcript.isNotEmpty()) {
            Spacer(Modifier.height(20.dp))
            Text(
                text = "\"$transcript\"",
                fontSize = 18.sp,
                color = Color.White,
                textAlign = TextAlign.Center,
                modifier = Modifier
                    .padding(horizontal = 24.dp)
                    .shadow(4.dp, RoundedCornerShape(10.dp), ambientColor = GolfGreen.copy(alpha = 0.2f), spotColor = GolfGreen.copy(alpha = 0.2f))
                    .clip(RoundedCornerShape(10.dp))
                    .background(DarkCard)
                    .border(1.dp, GolfGreenBorder, RoundedCornerShape(10.dp))
                    .padding(16.dp),
            )
        }

        Spacer(Modifier.weight(1f))

        // Correction card
        correction?.let { resp ->
            Column(
                modifier = Modifier
                    .padding(horizontal = 24.dp)
                    .shadow(8.dp, RoundedCornerShape(14.dp), ambientColor = GolfGreen.copy(alpha = 0.3f), spotColor = GolfGreen.copy(alpha = 0.3f))
                    .clip(RoundedCornerShape(14.dp))
                    .border(1.dp, GolfGreenBorder, RoundedCornerShape(14.dp))
                    .background(DarkCard)
                    .padding(20.dp),
            ) {
                if (resp.matched && resp.fault != null) {
                    Text(
                        text = resp.fault.uppercase().replace("_", " "),
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = GolfGreen,
                    )
                    Spacer(Modifier.height(8.dp))
                }
                Text(
                    text = resp.correction,
                    fontSize = 15.sp,
                    color = Color.White,
                )
                if (resp.matched) {
                    Spacer(Modifier.height(10.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        Row(
                            modifier = Modifier
                                .clip(RoundedCornerShape(8.dp))
                                .border(1.dp, GolfGreenBorder, RoundedCornerShape(8.dp))
                                .background(DarkBackground)
                                .clickable { shareCorrection(context, module, resp.fault ?: "", resp.correction) }
                                .padding(horizontal = 12.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Image(
                                painter = painterResource(id = R.drawable.ic_share),
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

            Spacer(Modifier.height(24.dp))
        }

        // Mic button
        Box(
            modifier = Modifier
                .size(88.dp)
                .then(if (isListening) Modifier.scale(pulseScale) else Modifier)
                .shadow(12.dp, CircleShape, ambientColor = if (isListening) Color.Red.copy(alpha = 0.4f) else GolfGreen.copy(alpha = 0.4f), spotColor = if (isListening) Color.Red.copy(alpha = 0.4f) else GolfGreen.copy(alpha = 0.4f))
                .border(2.dp, if (isListening) Color.Red else GolfGreen, CircleShape)
                .background(if (isListening) Color.Red.copy(alpha = 0.2f) else GolfGreen.copy(alpha = 0.15f), CircleShape)
                .clip(CircleShape)
                .clickable {
                    if (isListening) {
                        speechRecognizer.stopListening()
                        isListening = false
                    } else {
                        startListening()
                    }
                },
            contentAlignment = Alignment.Center,
        ) {
            if (isListening) {
                Icon(
                    Icons.Default.Stop,
                    contentDescription = "Stop",
                    tint = Color.Red,
                    modifier = Modifier.size(36.dp),
                )
            } else {
                Image(
                    painter = painterResource(id = R.drawable.ic_talk_mode),
                    contentDescription = "Start listening",
                    modifier = Modifier.size(44.dp),
                    contentScale = ContentScale.Fit,
                )
            }
        }

        Spacer(Modifier.height(48.dp))
    }
}

private fun shareCorrection(context: Context, module: GolfModule, fault: String, correction: String) {
    val text = buildString {
        appendLine("GolfCoachNow — ${module.title} Talk Mode")
        appendLine()
        if (fault.isNotEmpty()) {
            appendLine("Fault: ${fault.replace("_", " ").uppercase()}")
        }
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
