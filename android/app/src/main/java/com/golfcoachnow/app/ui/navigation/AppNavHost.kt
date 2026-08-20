package com.golfcoachnow.app.ui.navigation

import androidx.compose.runtime.Composable
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
    const val VIDEO = "video/{module}"
    const val CAMERA = "camera/{module}"
    const val PAYWALL = "paywall"
    const val LOGIN = "login"

    fun video(module: GolfModule) = "video/${module.name}"
    fun camera(module: GolfModule) = "camera/${module.name}"
}

@Composable
fun AppNavHost() {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = Routes.HOME) {
        composable(Routes.HOME) {
            HomeScreen(
                onLearn = {
                    navController.navigate(Routes.video(GolfModule.SWING))
                },
                onCorrect = {
                    navController.navigate(Routes.camera(GolfModule.SWING))
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
            arguments = listOf(navArgument("module") { type = NavType.StringType })
        ) { backStackEntry ->
            val moduleName = backStackEntry.arguments?.getString("module") ?: "SWING"
            val module = GolfModule.valueOf(moduleName)
            InstructionalVideoScreen(
                module = module,
                onFinished = { navController.popBackStack() },
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
