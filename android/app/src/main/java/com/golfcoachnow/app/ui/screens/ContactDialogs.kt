package com.golfcoachnow.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.golfcoachnow.app.data.api.ApiClient
import com.golfcoachnow.app.data.api.ApiException
import com.golfcoachnow.app.ui.theme.DarkCard
import com.golfcoachnow.app.ui.theme.GolfGreen
import com.golfcoachnow.app.ui.theme.TextMuted
import com.golfcoachnow.app.util.EntitlementManager
import kotlinx.coroutines.launch

/**
 * Turns a failed send into something worth reading.
 *
 * The server distinguishes these cases carefully, so throwing them all away as
 * "something went wrong" would waste that and leave people retyping a correct
 * address against a limit that has nothing to do with it.
 */
private fun explain(error: Throwable): String = when ((error as? ApiException)?.code) {
    422 -> "That doesn't look like a valid email address."
    429 -> "That's been sent a few times already. Try again a little later."
    503 -> "Sharing isn't switched on yet. Please try again soon."
    else -> "Couldn't send that. Check your connection and try again."
}

@Composable
private fun ContactDialog(
    title: String,
    confirmLabel: String,
    successMessage: String,
    canSubmit: Boolean,
    onDismiss: () -> Unit,
    submit: suspend () -> Result<*>,
    content: @Composable () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var sending by remember { mutableStateOf(false) }
    var sent by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = { if (!sending) onDismiss() },
        containerColor = DarkCard,
        title = { Text(title, color = Color.White) },
        text = {
            Column {
                if (sent) {
                    Text(successMessage, color = TextMuted, fontSize = 14.sp)
                } else {
                    content()
                    error?.let {
                        Spacer(Modifier.height(8.dp))
                        Text(it, color = Color(0xFFFF6B6B), fontSize = 13.sp)
                    }
                }
            }
        },
        confirmButton = {
            when {
                sent -> TextButton(onClick = onDismiss) {
                    Text("DONE", color = GolfGreen)
                }
                sending -> CircularProgressIndicator(
                    color = GolfGreen,
                    modifier = Modifier.height(24.dp),
                )
                else -> TextButton(
                    enabled = canSubmit,
                    onClick = {
                        error = null
                        sending = true
                        scope.launch {
                            val result = submit()
                            sending = false
                            result
                                .onSuccess { sent = true }
                                .onFailure { error = explain(it) }
                        }
                    },
                ) {
                    Text(
                        confirmLabel,
                        color = if (canSubmit) GolfGreen else TextMuted,
                    )
                }
            }
        },
        dismissButton = {
            if (!sent && !sending) {
                TextButton(onClick = onDismiss) { Text("CANCEL", color = TextMuted) }
            }
        },
    )
}

@Composable
fun ShareWithFriendDialog(onDismiss: () -> Unit) {
    var email by remember { mutableStateOf("") }

    ContactDialog(
        title = "Share with a friend",
        confirmLabel = "SEND",
        successMessage = "Sent. Your friend will get a link to the app.",
        // Not full validation: the server decides. This only stops an obviously
        // empty submission from costing somebody a round trip.
        canSubmit = email.contains("@") && email.length > 3,
        onDismiss = onDismiss,
        submit = { ApiClient.shareWithFriend(email.trim(), EntitlementManager.deviceId) },
    ) {
        Column {
            Text(
                "We'll email them a link to download Golf Coach Now.",
                color = TextMuted,
                fontSize = 13.sp,
            )
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Their email address") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
fun ConnectFounderDialog(onDismiss: () -> Unit) {
    var message by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }

    ContactDialog(
        title = "Connect with the founder",
        confirmLabel = "SEND",
        successMessage = "Thanks. Your message is on its way to the founder.",
        canSubmit = message.isNotBlank(),
        onDismiss = onDismiss,
        submit = {
            ApiClient.messageFounder(
                message = message.trim(),
                email = email.trim(),
                deviceId = EntitlementManager.deviceId,
            )
        },
    ) {
        Column {
            Text(
                "The founder welcomes your thoughts.",
                color = TextMuted,
                fontSize = 13.sp,
            )
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = message,
                onValueChange = { message = it },
                label = { Text("Your message") },
                minLines = 3,
                maxLines = 6,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                // Optional on purpose. Requiring it would stop somebody sending
                // feedback, which is the opposite of what this button is for.
                label = { Text("Your email (optional, for a reply)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}
