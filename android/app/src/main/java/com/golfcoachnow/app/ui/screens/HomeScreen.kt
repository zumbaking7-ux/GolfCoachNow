package com.golfcoachnow.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.GolfCourse
import androidx.compose.material.icons.filled.Landscape
import androidx.compose.material.icons.filled.SportsGolf
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.data.model.GolfModule
import com.golfcoachnow.app.ui.theme.DarkCard
import com.golfcoachnow.app.ui.theme.GolfGreen

@Composable
fun HomeScreen(onModuleSelected: (GolfModule) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 24.dp)
            .statusBarsPadding(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(48.dp))

        Text(
            text = "GolfCoachNow",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            color = GolfGreen,
        )

        Text(
            text = "Select your training mode",
            fontSize = 16.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 8.dp),
        )

        Spacer(Modifier.height(40.dp))

        ModuleCard(
            module = GolfModule.SWING,
            icon = Icons.Default.SportsGolf,
            onClick = {
                ApiClient.trackEvent("module_selected", GolfModule.SWING)
                onModuleSelected(GolfModule.SWING)
            },
        )

        Spacer(Modifier.height(16.dp))

        ModuleCard(
            module = GolfModule.PUTT,
            icon = Icons.Default.GolfCourse,
            onClick = {
                ApiClient.trackEvent("module_selected", GolfModule.PUTT)
                onModuleSelected(GolfModule.PUTT)
            },
        )

        Spacer(Modifier.height(16.dp))

        ModuleCard(
            module = GolfModule.SHORT_GAME,
            icon = Icons.Default.Landscape,
            onClick = {
                ApiClient.trackEvent("module_selected", GolfModule.SHORT_GAME)
                onModuleSelected(GolfModule.SHORT_GAME)
            },
        )
    }
}

@Composable
private fun ModuleCard(
    module: GolfModule,
    icon: ImageVector,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = DarkCard),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = icon,
                contentDescription = module.title,
                tint = GolfGreen,
                modifier = Modifier.size(40.dp),
            )
            Spacer(Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = module.title,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Text(
                    text = module.subtitle,
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Icon(
                imageVector = Icons.Default.SportsGolf,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(24.dp),
            )
        }
    }
}
