package com.golfcoachnow.app.ui.screens

import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.TrendingUp
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.ui.theme.GolfGreen
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
            .background(Color.Black)
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

        Spacer(Modifier.height(24.dp))

        Icon(
            Icons.Default.Lock,
            contentDescription = null,
            tint = GolfGreen,
            modifier = Modifier.size(64.dp),
        )

        Spacer(Modifier.height(16.dp))

        Text(
            text = "Unlock Full Access",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White,
        )

        Spacer(Modifier.height(8.dp))

        Text(
            text = "One-time payment. No subscriptions.",
            fontSize = 16.sp,
            color = Color.White.copy(alpha = 0.6f),
        )

        Spacer(Modifier.height(32.dp))

        FeatureRow(Icons.Default.SportsGolf, "Unlimited swing analysis")
        FeatureRow(Icons.Default.GolfCourse, "Unlimited putting analysis")
        FeatureRow(Icons.Default.Landscape, "Unlimited short game analysis")
        FeatureRow(Icons.Default.GraphicEq, "Talk Mode voice coaching")
        FeatureRow(Icons.Default.Share, "Share corrections")
        FeatureRow(Icons.AutoMirrored.Filled.TrendingUp, "Performance tracking")

        Spacer(Modifier.weight(1f))

        Text(
            text = "$14.99",
            fontSize = 48.sp,
            fontWeight = FontWeight.Bold,
            color = GolfGreen,
        )

        Text(
            text = "one-time purchase",
            fontSize = 14.sp,
            color = Color.White.copy(alpha = 0.6f),
        )

        Spacer(Modifier.height(24.dp))

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
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp),
            shape = RoundedCornerShape(16.dp),
            colors = ButtonDefaults.buttonColors(containerColor = GolfGreen),
            enabled = !isLoading,
        ) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = Color.White,
                    strokeWidth = 2.dp,
                )
            } else {
                Text(
                    text = "Unlock Now — $14.99",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        Spacer(Modifier.height(16.dp))

        TextButton(onClick = {
            scope.launch {
                EntitlementManager.checkRemoteStatus(context)
            }
        }) {
            Text(
                text = "Already purchased? Restore",
                color = GolfGreen,
                fontSize = 14.sp,
            )
        }
    }
}

@Composable
private fun FeatureRow(icon: ImageVector, text: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, tint = GolfGreen, modifier = Modifier.size(24.dp))
        Spacer(Modifier.width(12.dp))
        Text(text, color = Color.White, fontSize = 16.sp)
    }
}
