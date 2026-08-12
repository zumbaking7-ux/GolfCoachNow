package com.golfcoachnow.app

import android.app.Application
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.util.EntitlementManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class GolfCoachNowApp : Application() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        EntitlementManager.init(this)
        scope.launch {
            EntitlementManager.loadFromDisk(this@GolfCoachNowApp)
            EntitlementManager.checkRemoteStatus(this@GolfCoachNowApp)
            ApiClient.trackEvent("app_open")
        }
    }
}
