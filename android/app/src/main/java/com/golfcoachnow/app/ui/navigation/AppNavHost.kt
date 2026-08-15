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
import com.golfcoachnow.app.ui.screens.LoginScreen
import com.golfcoachnow.app.ui.screens.PaywallScreen
import com.golfcoachnow.app.ui.screens.TalkModeScreen

object Routes {
    const val HOME = "home"
    const val CAMERA = "camera/{module}"
    const val PAYWALL = "paywall"
    const val TALK = "talk/{module}"
    const val LOGIN = "login"

    fun camera(module: GolfModule) = "camera/${module.name}"
    fun talk(module: GolfModule) = "talk/${module.name}"
}

@Composable
fun AppNavHost() {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = Routes.HOME) {
        composable(Routes.HOME) {
            HomeScreen(
                onModuleSelected = { module ->
                    navController.navigate(Routes.camera(module))
                },
                onTalkMode = {
                    navController.navigate(Routes.talk(GolfModule.SWING))
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
            route = Routes.CAMERA,
            arguments = listOf(navArgument("module") { type = NavType.StringType })
        ) { backStackEntry ->
            val moduleName = backStackEntry.arguments?.getString("module") ?: "SWING"
            val module = GolfModule.valueOf(moduleName)
            CameraScreen(
                module = module,
                onBack = { navController.popBackStack() },
                onPaywall = { navController.navigate(Routes.PAYWALL) },
                onTalkMode = { navController.navigate(Routes.talk(module)) },
            )
        }

        composable(Routes.PAYWALL) {
            PaywallScreen(
                onBack = { navController.popBackStack() },
                onUnlocked = { navController.popBackStack() },
            )
        }

        composable(
            route = Routes.TALK,
            arguments = listOf(navArgument("module") { type = NavType.StringType })
        ) { backStackEntry ->
            val moduleName = backStackEntry.arguments?.getString("module") ?: "SWING"
            val module = GolfModule.valueOf(moduleName)
            TalkModeScreen(
                module = module,
                onBack = { navController.popBackStack() },
            )
        }
    }
}
