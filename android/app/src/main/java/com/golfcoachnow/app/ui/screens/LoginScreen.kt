package com.golfcoachnow.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.ui.theme.*
import com.golfcoachnow.app.util.AuthManager
import com.golfcoachnow.app.util.EntitlementManager
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(
    onBack: () -> Unit,
    onSignedIn: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var email by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    // Set once the code has been accepted and the account turns out to have no
    // name yet. Asked here rather than on the sign in form: the only way to
    // know beforehand is to ask the server whether the address is known, which
    // answers that question for anybody who asks.
    var askingForName by remember { mutableStateOf(false) }
    var codeSent by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            // Same reason as the home screen: the content is drawn behind the
            // system bars unless something says otherwise.
            .safeDrawingPadding()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(16.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) {
                Text("←", color = GolfGreen, fontSize = 24.sp)
            }
            Spacer(Modifier.weight(1f))
        }

        Spacer(Modifier.height(48.dp))

        Text(
            text = if (askingForName) "Almost there" else if (codeSent) "Enter Code" else "Sign In",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White,
        )

        Spacer(Modifier.height(8.dp))

        Text(
            text = if (askingForName) "What should we call you?"
            else if (codeSent) "We sent a 6-digit code to\n$email"
                   else "Enter your email to receive\na sign-in code",
            fontSize = 15.sp,
            color = TextMuted,
            textAlign = TextAlign.Center,
            lineHeight = 22.sp,
        )

        Spacer(Modifier.height(32.dp))

        if (askingForName) {
            OutlinedTextField(
                value = name,
                onValueChange = { if (it.length <= 80) name = it },
                label = { Text("Your first name") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Text,
                    imeAction = ImeAction.Done,
                ),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = GolfGreen,
                    unfocusedBorderColor = GolfGreenBorder,
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                    cursorColor = GolfGreen,
                    focusedLabelColor = GolfGreen,
                    unfocusedLabelColor = TextMuted,
                ),
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(20.dp))

            GreenButton(
                text = "Continue",
                enabled = !loading,
                loading = loading,
                onClick = {
                    val typed = name.trim()
                    if (typed.isEmpty()) {
                        onSignedIn()
                    } else {
                        loading = true
                        scope.launch {
                            ApiClient.setName(typed).onSuccess {
                                AuthManager.save(context, AuthManager.token.orEmpty(), email, typed)
                            }
                            loading = false
                            // Signed in either way. A name is a nicety, and
                            // failing to store one must not strand somebody
                            // who has already proved who they are.
                            onSignedIn()
                        }
                    }
                },
            )

            Spacer(Modifier.height(16.dp))

            TextButton(onClick = { onSignedIn() }) {
                Text("Skip for now", color = GolfGreen, fontSize = 14.sp)
            }
        } else if (!codeSent) {
            OutlinedTextField(
                value = email,
                onValueChange = { email = it.trim(); error = null },
                label = { Text("Email address") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Email,
                    imeAction = ImeAction.Go,
                ),
                keyboardActions = KeyboardActions(onGo = {
                    if (email.contains("@")) {
                        loading = true
                        error = null
                        scope.launch {
                            val result = ApiClient.requestCode(email)
                            loading = false
                            result.onSuccess {
                                codeSent = true
                            }
                            result.onFailure { error = it.message ?: "Failed to send code" }
                        }
                    }
                }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = GolfGreen,
                    unfocusedBorderColor = GolfGreenBorder,
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                    cursorColor = GolfGreen,
                    focusedLabelColor = GolfGreen,
                    unfocusedLabelColor = TextMuted,
                ),
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(20.dp))

            GreenButton(
                text = "Send Code",
                enabled = email.contains("@") && !loading,
                loading = loading,
                onClick = {
                    loading = true
                    error = null
                    scope.launch {
                        val result = ApiClient.requestCode(email)
                        loading = false
                        result.onSuccess {
                            codeSent = true
                        }
                        result.onFailure { error = it.message ?: "Failed to send code" }
                    }
                },
            )
        } else {
            OutlinedTextField(
                value = code,
                onValueChange = { if (it.length <= 6) { code = it.filter { c -> c.isDigit() }; error = null } },
                label = { Text("6-digit code") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Number,
                    imeAction = ImeAction.Go,
                ),
                keyboardActions = KeyboardActions(onGo = {
                    if (code.length == 6) {
                        loading = true
                        error = null
                        scope.launch {
                            val result = ApiClient.verifyCode(email, code, EntitlementManager.deviceId)
                            loading = false
                            result.onSuccess { resp ->
                                AuthManager.save(context, resp.token, email, resp.name)
                                if (resp.name.isNullOrBlank()) askingForName = true else onSignedIn()
                            }
                            result.onFailure { error = it.message ?: "Invalid code" }
                        }
                    }
                }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = GolfGreen,
                    unfocusedBorderColor = GolfGreenBorder,
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                    cursorColor = GolfGreen,
                    focusedLabelColor = GolfGreen,
                    unfocusedLabelColor = TextMuted,
                ),
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(20.dp))

            GreenButton(
                text = "Verify",
                enabled = code.length == 6 && !loading,
                loading = loading,
                onClick = {
                    loading = true
                    error = null
                    scope.launch {
                        val result = ApiClient.verifyCode(email, code, EntitlementManager.deviceId)
                        loading = false
                        result.onSuccess { resp ->
                            AuthManager.save(context, resp.token, email, resp.name)
                            if (resp.name.isNullOrBlank()) askingForName = true else onSignedIn()
                        }
                        result.onFailure { error = it.message ?: "Invalid code" }
                    }
                },
            )

            Spacer(Modifier.height(16.dp))

            TextButton(onClick = {
                codeSent = false
                code = ""
                name = ""
                error = null
            }) {
                Text("Use different email", color = GolfGreen, fontSize = 14.sp)
            }
        }

        if (error != null) {
            Spacer(Modifier.height(16.dp))
            Text(
                text = error!!,
                color = Color(0xFFFF3B30),
                fontSize = 14.sp,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun GreenButton(
    text: String,
    enabled: Boolean,
    loading: Boolean,
    onClick: () -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(52.dp)
            .clip(RoundedCornerShape(14.dp))
            .then(
                if (enabled) Modifier
                    .border(1.dp, Color(0xFF618C1F), RoundedCornerShape(14.dp))
                    .background(Brush.verticalGradient(listOf(Color(0xFF8FC238), Color(0xFF6B9E24))))
                else Modifier.background(Color(0xFF333333))
            ),
        contentAlignment = Alignment.Center,
    ) {
        Button(
            onClick = onClick,
            enabled = enabled && !loading,
            colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent, disabledContainerColor = Color.Transparent),
            modifier = Modifier.fillMaxSize(),
        ) {
            if (loading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(22.dp),
                    strokeWidth = 2.dp,
                    color = Color.Black,
                )
            } else {
                Text(
                    text = text,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (enabled) Color.Black else TextMuted,
                )
            }
        }
    }
}
