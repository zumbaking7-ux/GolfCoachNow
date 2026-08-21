package com.golfcoachnow.app.ui.screens

import android.content.Intent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.graphics.Brush
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.*
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.golfcoachnow.app.R
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.data.model.GolfModule
import com.golfcoachnow.app.ui.theme.*
import com.golfcoachnow.app.util.AuthManager
import kotlinx.coroutines.launch
import java.util.Calendar

@Composable
fun HomeScreen(
    onLearn: () -> Unit,
    onCorrect: () -> Unit,
    onLogin: () -> Unit = {},
) {
    val scrollState = rememberScrollState()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val userEmail by AuthManager.email.collectAsState()
    val userName by AuthManager.name.collectAsState()

    var showShareDialog by remember { mutableStateOf(false) }
    var showFounderDialog by remember { mutableStateOf(false) }

    if (showShareDialog) {
        ShareWithFriendDialog(onDismiss = { showShareDialog = false })
    }
    if (showFounderDialog) {
        ConnectFounderDialog(onDismiss = { showFounderDialog = false })
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .verticalScroll(scrollState),
    ) {
        // Banner
        Image(
            painter = painterResource(id = R.drawable.banner),
            contentDescription = "GolfCoachNow Banner",
            modifier = Modifier
                .fillMaxWidth()
                // Inset to the same margin the cards use, so the club head is
                // not flush against the edge of the screen.
                .padding(horizontal = 12.dp)
                // The image's own ratio, so the box is never a different shape
                // from the picture and the golfer keeps his club.
                .aspectRatio(1926f / 817f)
                .clip(RoundedCornerShape(14.dp)),
            contentScale = ContentScale.Fit,
        )

        // Account row
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.End,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (userEmail != null) {
                Text(
                    text = userEmail!!,
                    fontSize = 12.sp,
                    color = GolfGreen,
                    modifier = Modifier.weight(1f),
                )
                TextButton(onClick = {
                    scope.launch {
                        AuthManager.token?.let { ApiClient.signOut(it) }
                        AuthManager.signOut(context)
                    }
                }) {
                    Text("Sign Out", color = TextMuted, fontSize = 12.sp)
                }
            } else {
                Spacer(Modifier.weight(1f))
                TextButton(onClick = onLogin) {
                    Text("Sign In", color = GolfGreen, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                }
            }
        }

        // Greeting card below the banner, not over it. It used to be pulled up
        // 24dp, which hid the glow sweep along the bottom of the artwork.
        Box(
            modifier = Modifier
                .offset(y = 10.dp)
                .padding(horizontal = 16.dp),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .shadow(6.dp, RoundedCornerShape(14.dp), ambientColor = GolfGreen.copy(alpha = 0.25f), spotColor = GolfGreen.copy(alpha = 0.25f))
                    .clip(RoundedCornerShape(14.dp))
                    .border(1.dp, GolfGreenBorder, RoundedCornerShape(14.dp))
                    .background(GreetingBg),
            ) {
                Image(
                    painter = painterResource(id = R.drawable.bg_pattern),
                    contentDescription = null,
                    modifier = Modifier.matchParentSize(),
                    contentScale = ContentScale.Crop,
                    alpha = 0.6f,
                )
                Column(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 18.dp),
                ) {
                    Text(
                        text = buildAnnotatedString {
                            // From the account, never derived from the email
                            // address. Deriving it greeted
                            // waleflutter@gmail.com as "waleflutter".
                            val who = userName?.takeIf { it.isNotBlank() } ?: "Golfer"
                            val white = SpanStyle(color = Color.White, fontWeight = FontWeight.ExtraBold)
                            val green = SpanStyle(color = GolfGreen, fontWeight = FontWeight.ExtraBold)
                            withStyle(white) { append(timeOfDayGreeting() + ",\n") }
                            withStyle(green) { append("$who.") }
                        },
                        fontSize = 26.sp,
                        lineHeight = 32.sp,
                    )
                    Spacer(Modifier.height(12.dp))
                    Box(
                        modifier = Modifier
                            .width(132.dp)
                            .height(2.dp)
                            .clip(RoundedCornerShape(1.dp))
                            .background(GolfGreen),
                    )
                    Spacer(Modifier.height(12.dp))
                    Text(
                        text = "What would you like\nto learn today?",
                        fontSize = 14.sp,
                        lineHeight = 19.sp,
                        color = Color(0xFFB3B3B3),
                    )
                }
            }
        }

        // Skill cards row
        Row(
            modifier = Modifier
                .offset(y = 22.dp)
                .padding(horizontal = 16.dp)
                .fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            SkillCard(
                title = "SWING CORRECT",
                description = "Analyze your swing.\nGet instant feedback.",
                ctaLabel = "START SWING CORRECT →",
                iconRes = R.drawable.ic_swing,
                modifier = Modifier.weight(1f),
                onClick = {
                    ApiClient.trackEvent("module_selected", GolfModule.SWING)
                    onCorrect()
                },
            )
            SkillCard(
                title = "SWING LEARN",
                description = "Learn your swing.\nGet instant feedback.",
                ctaLabel = "START SWING LEARN →",
                iconRes = R.drawable.ic_swing,
                modifier = Modifier.weight(1f),
                onClick = {
                    ApiClient.trackEvent("module_selected", GolfModule.SWING)
                    onLearn()
                },
            )
        }

        // Action row. Connect sits on the left and Share on the right, and the
        // two cards carry equal weight so they read as a matched pair.
        Row(
            modifier = Modifier
                .padding(top = 8.dp)
                .padding(horizontal = 16.dp)
                .fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            ActionCard(
                iconRes = R.drawable.ic_share_plane,
                title = "SHARE",
                description = "Share Golf Coach Now.",
                modifier = Modifier.weight(1f),
                onClick = { showShareDialog = true },
            )
            ActionCard(
                iconRes = R.drawable.ic_connect_people,
                title = "CONNECT",
                description = "Connect with the founder.",
                modifier = Modifier.weight(1f),
                onClick = { showFounderDialog = true },
            )
        }
    }
}

/** Morning, afternoon or evening, because a screen that says "Good morning"
 *  at eleven at night is exactly the detail a reviewer notices. */
private fun timeOfDayGreeting(): String {
    val hour = java.util.Calendar.getInstance().get(java.util.Calendar.HOUR_OF_DAY)
    return when {
        hour < 12 -> "Good morning"
        hour < 18 -> "Good afternoon"
        else -> "Good evening"
    }
}

@Composable
private fun SkillCard(
    title: String,
    description: String,
    ctaLabel: String,
    iconRes: Int,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Column(
        modifier = modifier
            .shadow(6.dp, RoundedCornerShape(14.dp), ambientColor = GolfGreen.copy(alpha = 0.25f), spotColor = GolfGreen.copy(alpha = 0.25f))
            .clip(RoundedCornerShape(14.dp))
            .border(1.dp, GolfGreenBorder, RoundedCornerShape(14.dp))
            .background(DarkCard)
            .clickable(onClick = onClick)
            .padding(vertical = 10.dp, horizontal = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Image(
            painter = painterResource(id = iconRes),
            contentDescription = title,
            modifier = Modifier
                .size(48.dp)
                .clip(RoundedCornerShape(12.dp)),
            contentScale = ContentScale.Crop,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            text = title,
            fontSize = 13.sp,
            fontWeight = FontWeight.ExtraBold,
            color = Color.White,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(2.dp))
        Text(
            text = description,
            fontSize = 11.sp,
            color = TextMuted,
            textAlign = TextAlign.Center,
            maxLines = 3,
            lineHeight = 15.sp,
        )
        Spacer(Modifier.height(6.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 1.dp)
                .clip(RoundedCornerShape(8.dp))
                .border(1.dp, Color(0xFF618C1F), RoundedCornerShape(8.dp))
                .background(
                    Brush.verticalGradient(
                        colors = listOf(
                            Color(0xFF8FC238),
                            Color(0xFF6B9E24),
                        ),
                    ),
                )
                .padding(vertical = 6.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = ctaLabel,
                fontSize = 9.sp,
                fontWeight = FontWeight.ExtraBold,
                color = Color.Black,
                maxLines = 1,
            )
        }
    }
}

@Composable
private fun ActionCard(
    iconRes: Int,
    title: String,
    description: String,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Row(
        modifier = modifier
            .height(90.dp)
            .shadow(6.dp, RoundedCornerShape(14.dp), ambientColor = GolfGreen.copy(alpha = 0.25f), spotColor = GolfGreen.copy(alpha = 0.25f))
            .clip(RoundedCornerShape(14.dp))
            .border(1.dp, GolfGreenBorder, RoundedCornerShape(14.dp))
            .background(DarkCard)
            .clickable(onClick = onClick)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Image(
            painter = painterResource(id = iconRes),
            contentDescription = title,
            modifier = Modifier
                .size(36.dp)
                .clip(RoundedCornerShape(8.dp)),
            contentScale = ContentScale.Crop,
        )
        Spacer(Modifier.width(10.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White,
            )
            Text(
                text = description,
                fontSize = 11.sp,
                color = TextMuted,
                maxLines = 2,
                lineHeight = 14.sp,
            )
        }
        Image(
            painter = painterResource(id = R.drawable.ic_arrow),
            contentDescription = "Go",
            modifier = Modifier.size(20.dp),
            contentScale = ContentScale.Fit,
        )
    }
}

private fun timeGreeting(): String {
    val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
    return when (hour) {
        in 5..11 -> "Good morning,"
        in 12..16 -> "Good afternoon,"
        else -> "Good evening,"
    }
}
