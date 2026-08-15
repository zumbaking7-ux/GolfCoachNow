package com.golfcoachnow.app

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.lifecycleScope
import androidx.navigation.compose.rememberNavController
import com.golfcoachnow.app.ui.navigation.AppNavHost
import com.golfcoachnow.app.ui.theme.GolfCoachNowTheme
import com.golfcoachnow.app.util.EntitlementManager
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private var pendingDeepLink by mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        handleIntent(intent)

        setContent {
            GolfCoachNowTheme {
                AppNavHost()
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        val uri = intent?.data ?: return
        if (uri.scheme != "golfcoachnow") return

        when (uri.host) {
            "payment-success" -> {
                lifecycleScope.launch {
                    EntitlementManager.markUnlocked(this@MainActivity)
                    Toast.makeText(
                        this@MainActivity,
                        "Full access unlocked!",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
            "payment-cancelled" -> {
                Toast.makeText(this, "Payment cancelled", Toast.LENGTH_SHORT).show()
            }
        }
    }
}
