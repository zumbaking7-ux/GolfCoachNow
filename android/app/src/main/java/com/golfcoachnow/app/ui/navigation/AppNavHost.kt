package com.golfcoachnow.app.ui.navigation

import android.widget.Toast
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.golfcoachnow.app.data.model.GolfModule
import com.golfcoachnow.app.ui.screens.CameraScreen
import com.golfcoachnow.app.ui.screens.HomeScreen
import com.golfcoachnow.app.ui.screens.InstructionalVideoScreen
import com.golfcoachnow.app.ui.screens.LoginScreen
import com.golfcoachnow.app.ui.screens.PaywallScreen

object Routes {
    const val HOME = "home"
    const val VIDEO = "video/{module}?next={next}"
    const val NEXT_HOME = "home"
    const val NEXT_CAMERA = "camera"
    const val CAMERA = "camera/{module}"
    const val PAYWALL = "paywall"
    const val LOGIN = "login"

    fun video(module: GolfModule, next: String) = "video/${module.name}?next=$next"
    fun camera(module: GolfModule) = "camera/${module.name}"
}

@Composable
fun AppNavHost() {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = Routes.HOME) {
        composable(Routes.HOME) {
            HomeScreen(
                onLearn = {
                    navController.navigate(Routes.video(GolfModule.SWING, Routes.NEXT_HOME))
                },
                onCorrect = {
                    navController.navigate(Routes.video(GolfModule.SWING, Routes.NEXT_CAMERA))
                },
                onLogin = {
                    navController.navigate(Routes.LOGIN)
                },
            )
        }

        composable(Routes.LOGIN) {
            LoginScreen(
                onBack = { navController.popBackStack() },
                onSignedIn = { navController.popBackStack() },
            )
        }

        composable(
            route = Routes.VIDEO,
            arguments = listOf(
                navArgument("module") { type = NavType.StringType },
                navArgument("next") {
                    type = NavType.StringType
                    defaultValue = Routes.NEXT_HOME
                },
            )
        ) { backStackEntry ->
            val moduleName = backStackEntry.arguments?.getString("module") ?: "SWING"
            val module = GolfModule.valueOf(moduleName)
            val next = backStackEntry.arguments?.getString("next") ?: Routes.NEXT_HOME
            val context = LocalContext.current

            // Swing Correct plays its clip and then records. Swing Learn ends
            // with its own. They are different clips, chosen from `next` below.
            val goOn: () -> Unit = if (next == Routes.NEXT_CAMERA) {
                {
                    // Replace the video in the back stack rather than stacking
                    // on top of it, so backing out of the camera returns home
                    // instead of replaying the clip just watched.
                    navController.navigate(Routes.camera(module)) {
                        popUpTo(Routes.VIDEO) { inclusive = true }
                    }
                }
            } else {
                { navController.popBackStack() }
            }

            InstructionalVideoScreen(
                module = module,
                // The route already knows which button opened this, and the
                // two play different clips: Swing Learn opens the lesson,
                // Swing Correct opens the clip about framing the shot.
                screen = if (next == Routes.NEXT_CAMERA) "correct" else "learn",
                onFinished = goOn,
                onUnavailable = {
                    // Ahead of the camera a missing clip is skipped in silence;
                    // recording must never wait on a coaching video. Reached on
                    // its own it has to be said out loud, or Swing Learn looks
                    // like a button that does nothing.
                    if (next != Routes.NEXT_CAMERA) {
                        Toast.makeText(
                            context,
                            "The lesson video is on its way. Try Swing Correct in the meantime.",
                            Toast.LENGTH_LONG,
                        ).show()
                    }
                    goOn()
                },
            )
        }

        composable(
            route = Routes.CAMERA,
            arguments = listOf(navArgument("module") { type = NavType.StringType })
        ) { backStackEntry ->
            val moduleName = backStackEntry.arguments?.getString("module") ?: "SWING"
            val module = GolfModule.valueOf(moduleName)
            CameraScreen(
                module = module,
                onBack = { navController.popBackStack() },
                onPaywall = { navController.navigate(Routes.PAYWALL) },
                onSignIn = { navController.navigate(Routes.LOGIN) },
            )
        }

        composable(Routes.PAYWALL) {
            PaywallScreen(
                onBack = { navController.popBackStack() },
                onUnlocked = { navController.popBackStack() },
            )
        }
    }
}
