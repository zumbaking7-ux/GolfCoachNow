package com.golfcoachnow.app.ui.screens

import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.golfcoachnow.app.R
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.ui.theme.*
import com.golfcoachnow.app.util.EntitlementManager
import kotlinx.coroutines.launch

@Composable
fun PaywallScreen(
    onBack: () -> Unit,
    onUnlocked: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var isLoading by remember { mutableStateOf(false) }
    val isUnlocked by EntitlementManager.isUnlocked.collectAsState()

    LaunchedEffect(isUnlocked) {
        if (isUnlocked) onUnlocked()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(modifier = Modifier.fillMaxWidth()) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = Color.White)
            }
        }

        Spacer(Modifier.height(16.dp))

        Image(
            painter = painterResource(id = R.drawable.banner),
            contentDescription = null,
            modifier = Modifier
                .fillMaxWidth()
                .height(100.dp)
                .clip(RoundedCornerShape(14.dp)),
            contentScale = ContentScale.Crop,
        )

        Spacer(Modifier.height(24.dp))

        Text(
            text = "UNLOCK FULL ACCESS",
            fontSize = 26.sp,
            fontWeight = FontWeight.ExtraBold,
            color = Color.White,
            letterSpacing = 1.sp,
        )

        Spacer(Modifier.height(6.dp))

        Text(
            text = "Train like a pro with unlimited AI coaching",
            fontSize = 14.sp,
            color = TextMuted,
            textAlign = TextAlign.Center,
        )

        Spacer(Modifier.height(24.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .shadow(6.dp, RoundedCornerShape(14.dp), ambientColor = GolfGreen.copy(alpha = 0.25f), spotColor = GolfGreen.copy(alpha = 0.25f))
                .clip(RoundedCornerShape(14.dp))
                .border(1.dp, GolfGreenBorder, RoundedCornerShape(14.dp))
                .background(DarkCard)
                .padding(16.dp),
        ) {
            FeatureRow(R.drawable.ic_swing, "Unlimited swing analysis")
            FeatureRow(R.drawable.ic_putt, "Unlimited putting analysis")
            FeatureRow(R.drawable.ic_short_game, "Unlimited short game analysis")
            FeatureRow(R.drawable.ic_share, "Share corrections")
        }

        Spacer(Modifier.weight(1f))

        Text(
            text = "$14.99",
            fontSize = 48.sp,
            fontWeight = FontWeight.ExtraBold,
            color = GolfGreen,
        )

        Text(
            text = "per month",
            fontSize = 14.sp,
            color = TextMuted,
        )

        Spacer(Modifier.height(20.dp))

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .shadow(8.dp, RoundedCornerShape(14.dp), ambientColor = GolfGreen.copy(alpha = 0.4f), spotColor = GolfGreen.copy(alpha = 0.4f))
                .clip(RoundedCornerShape(14.dp))
                .border(1.dp, Color(0xFF618C1F), RoundedCornerShape(14.dp))
                .background(
                    Brush.verticalGradient(
                        colors = listOf(
                            Color(0xFF8FC238),
                            Color(0xFF6B9E24),
                        ),
                    ),
                )
                .then(
                    if (!isLoading) Modifier.run {
                        this
                    } else Modifier
                ),
            contentAlignment = Alignment.Center,
        ) {
            Button(
                onClick = {
                    isLoading = true
                    scope.launch {
                        val result = ApiClient.createCheckoutSession(EntitlementManager.deviceId)
                        result.onSuccess { response ->
                            val intent = CustomTabsIntent.Builder().build()
                            intent.launchUrl(context, Uri.parse(response.checkoutUrl))
                        }.onFailure {
                            isLoading = false
                        }
                        isLoading = false
                    }
                },
                modifier = Modifier.fillMaxSize(),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent),
                enabled = !isLoading,
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        color = Color.Black,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Text(
                        text = "SUBSCRIBE NOW",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.ExtraBold,
                        color = Color.Black,
                        letterSpacing = 1.sp,
                    )
                    Spacer(Modifier.width(8.dp))
                    Image(
                        painter = painterResource(id = R.drawable.ic_arrow),
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                        contentScale = ContentScale.Fit,
                    )
                }
            }
        }

        Spacer(Modifier.height(12.dp))

        TextButton(onClick = {
            scope.launch {
                EntitlementManager.checkRemoteStatus(context)
            }
        }) {
            Text(
                text = "Already subscribed? Restore",
                color = GolfGreen,
                fontSize = 14.sp,
            )
        }
    }
}

@Composable
private fun FeatureRow(iconRes: Int, text: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Image(
            painter = painterResource(id = iconRes),
            contentDescription = null,
            modifier = Modifier.size(24.dp),
            contentScale = ContentScale.Fit,
        )
        Spacer(Modifier.width(12.dp))
        Text(text, color = Color.White, fontSize = 15.sp)
    }
}
