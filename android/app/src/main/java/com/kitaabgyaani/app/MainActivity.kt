package com.kitaabgyaani.app

import android.app.Activity
import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.gson.Gson
import com.kitaabgyaani.app.data.model.*
import com.kitaabgyaani.app.data.network.WebSocketClient
import com.kitaabgyaani.app.ui.theme.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.util.*

class MainActivity : ComponentActivity(), TextToSpeech.OnInitListener {

    private lateinit var tts: TextToSpeech
    private var webSocketClient: WebSocketClient? = null
    private val gson = Gson()
    private val httpClient = OkHttpClient()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        tts = TextToSpeech(this, this)

        setContent {
            KitaabGyaaniTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    ChatAppScreen()
                }
            }
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts.language = Locale.US
        }
    }

    fun speak(text: String) {
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, null)
    }

    override fun onDestroy() {
        tts.stop()
        tts.shutdown()
        webSocketClient?.disconnect()
        super.onDestroy()
    }

    data class ChatMessage(
        val id: String = UUID.randomUUID().toString(),
        val sender: String,
        val text: String,
        val bitmap: Bitmap? = null,
        val isSystem: Boolean = false
    )

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    fun ChatAppScreen() {
        val context = LocalContext.current
        var serverIp by remember { mutableStateOf("10.0.2.2") }
        var isConnected by remember { mutableStateOf(false) }
        var currentAgent by remember { mutableStateOf("study") }
        var inputText by remember { mutableStateOf("") }

        val chatHistories = remember {
            mutableStateMapOf<String, List<ChatMessage>>().apply {
                put("study", listOf(ChatMessage(sender = "agent", text = "Hello! Send me notes, or take a picture of study material to extract flashcards and summary.")))
                put("planner", listOf(ChatMessage(sender = "agent", text = "Hello! Send me your exam syllabus topics and target date to generate a study plan.")))
                put("expense", listOf(ChatMessage(sender = "agent", text = "Hello! Take a photo of a receipt to parse amount, category, and merchant details.")))
                put("content", listOf(ChatMessage(sender = "agent", text = "Hello! Describe the writing task and context to draft a professional copy.")))
            }
        }

        val currentHistory = chatHistories[currentAgent] ?: emptyList()
        val listState = rememberLazyListState()

        val webSocketListener = remember {
            object : WebSocketClient.WebSocketListenerInterface {
                override fun onConnected() {
                    isConnected = true
                    runOnUiThread { Toast.makeText(context, "Connected to KitaabGyaani Server", Toast.LENGTH_SHORT).show() }
                }

                override fun onDisconnected() {
                    isConnected = false
                    runOnUiThread { Toast.makeText(context, "Disconnected from Server", Toast.LENGTH_SHORT).show() }
                }

                override fun onMessageReceived(text: String) {
                    runOnUiThread {
                        try {
                            val wsResponse = gson.fromJson(text, WebSocketResponse::class.java)
                            val agentName = wsResponse.agent
                            val dataVal = wsResponse.data
                            val responseString = gson.toJson(dataVal)
                            val formattedText = formatAgentResponse(agentName, responseString)
                            
                            val history = chatHistories[agentName] ?: emptyList()
                            chatHistories[agentName] = history + ChatMessage(sender = "agent", text = formattedText)
                        } catch (e: Exception) {
                            val history = chatHistories[currentAgent] ?: emptyList()
                            chatHistories[currentAgent] = history + ChatMessage(sender = "agent", text = text)
                        }
                    }
                }

                override fun onError(error: String) {
                    isConnected = false
                    runOnUiThread { Toast.makeText(context, "WS Error: $error", Toast.LENGTH_SHORT).show() }
                }
            }
        }

        LaunchedEffect(serverIp) {
            webSocketClient?.disconnect()
            webSocketClient = WebSocketClient(webSocketListener)
            try {
                webSocketClient?.connect("ws://$serverIp:8000/ws")
            } catch (e: Exception) {
                isConnected = false
            }
        }

        LaunchedEffect(currentHistory.size) {
            if (currentHistory.isNotEmpty()) {
                listState.animateScrollToItem(currentHistory.size - 1)
            }
        }

        val speechLauncher = rememberLauncherForActivityResult(
            contract = ActivityResultContracts.StartActivityForResult()
        ) { result ->
            if (result.resultCode == Activity.RESULT_OK) {
                val matches = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                val voiceText = matches?.firstOrNull() ?: ""
                inputText = voiceText
            }
        }

        val cameraLauncher = rememberLauncherForActivityResult(
            contract = ActivityResultContracts.TakePicturePreview()
        ) { bitmap: Bitmap? ->
            bitmap?.let { capturedBitmap ->
                val base64 = bitmapToBase64(capturedBitmap)
                val history = chatHistories[currentAgent] ?: emptyList()
                chatHistories[currentAgent] = history + ChatMessage(sender = "user", text = "Captured Image for analysis", bitmap = capturedBitmap)

                if (isConnected) {
                    val payload = if (currentAgent == "expense") {
                        mapOf("image_base64" to base64)
                    } else {
                        mapOf("file_base64" to base64, "is_image" to true)
                    }
                    webSocketClient?.send(
                        WebSocketRequest(
                            id = UUID.randomUUID().toString(),
                            agent = currentAgent,
                            action = if (currentAgent == "expense") "process_receipt" else "process_material",
                            payload = payload
                        )
                    )
                } else {
                    val url = if (currentAgent == "expense") {
                        "http://$serverIp:8000/api/agents/expense/process"
                    } else {
                        "http://$serverIp:8000/api/agents/study/process"
                    }
                    val bodyJson = if (currentAgent == "expense") {
                        gson.toJson(mapOf("image_base64" to base64))
                    } else {
                        gson.toJson(mapOf("content" to base64, "is_image" to true))
                    }
                    makeHttpRequest(
                        url = url,
                        bodyJson = bodyJson,
                        onSuccess = { res ->
                            val formattedText = formatAgentResponse(currentAgent, res)
                            runOnUiThread {
                                val currentList = chatHistories[currentAgent] ?: emptyList()
                                chatHistories[currentAgent] = currentList + ChatMessage(sender = "agent", text = formattedText)
                            }
                        },
                        onError = { err ->
                            runOnUiThread {
                                val currentList = chatHistories[currentAgent] ?: emptyList()
                                chatHistories[currentAgent] = currentList + ChatMessage(sender = "agent", text = "Error: $err")
                            }
                        }
                    )
                }
            }
        }

        val filePickerLauncher = rememberLauncherForActivityResult(
            contract = ActivityResultContracts.GetContent()
        ) { uri: Uri? ->
            uri?.let {
                val contentResolver = context.contentResolver
                val base64 = uriToBase64(it, contentResolver)
                if (base64 != null) {
                    val isImage = contentResolver.getType(it)?.startsWith("image/") == true
                    val history = chatHistories[currentAgent] ?: emptyList()
                    chatHistories[currentAgent] = history + ChatMessage(sender = "user", text = "Uploaded file for processing")

                    if (isConnected) {
                        webSocketClient?.send(
                            WebSocketRequest(
                                id = UUID.randomUUID().toString(),
                                agent = "study",
                                action = "process_material",
                                payload = mapOf("file_base64" to base64, "is_image" to isImage)
                            )
                        )
                    } else {
                        makeHttpRequest(
                            url = "http://$serverIp:8000/api/agents/study/process",
                            bodyJson = gson.toJson(mapOf("content" to base64, "is_image" to isImage)),
                            onSuccess = { res ->
                                val formattedText = formatAgentResponse("study", res)
                                runOnUiThread {
                                    val currentList = chatHistories[currentAgent] ?: emptyList()
                                    chatHistories[currentAgent] = currentList + ChatMessage(sender = "agent", text = formattedText)
                                }
                            },
                            onError = { err ->
                                runOnUiThread {
                                    val currentList = chatHistories[currentAgent] ?: emptyList()
                                    chatHistories[currentAgent] = currentList + ChatMessage(sender = "agent", text = "Error: $err")
                                }
                            }
                        )
                    }
                }
            }
        }

        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text("KitaabGyaani Chat", fontWeight = FontWeight.Bold, color = TextLight, fontSize = 18.sp)
                            Row(
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(6.dp)
                                        .clip(RoundedCornerShape(3.dp))
                                        .background(if (isConnected) AccentEmerald else Color.Red)
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(
                                    if (isConnected) "Connected to server" else "Offline mode",
                                    fontSize = 11.sp,
                                    color = if (isConnected) AccentEmerald else TextMuted
                                )
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkSurface),
                    actions = {
                        IconButton(onClick = { filePickerLauncher.launch("*/*") }) {
                            Icon(Icons.Default.Share, contentDescription = "Upload Document", tint = TextLight)
                        }
                    }
                )
            },
            bottomBar = {
                Column(
                    modifier = Modifier
                        .background(DarkSurface)
                        .padding(horizontal = 8.dp, vertical = 8.dp)
                        .navigationBarsPadding()
                        .imePadding()
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        IconButton(
                            onClick = { cameraLauncher.launch(null) },
                            colors = IconButtonDefaults.iconButtonColors(containerColor = DarkBackground)
                        ) {
                            Icon(Icons.Default.CameraAlt, contentDescription = "Camera", tint = SecondaryCyan)
                        }

                        IconButton(
                            onClick = {
                                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                                }
                                speechLauncher.launch(intent)
                            },
                            colors = IconButtonDefaults.iconButtonColors(containerColor = DarkBackground)
                        ) {
                            Icon(Icons.Default.PlayArrow, contentDescription = "Voice", tint = SecondaryCyan)
                        }

                        OutlinedTextField(
                            value = inputText,
                            onValueChange = { inputText = it },
                            placeholder = { Text("Ask anything to ${currentAgent}...", color = TextMuted) },
                            maxLines = 3,
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                            keyboardActions = KeyboardActions(onSend = {
                                if (inputText.isNotEmpty()) {
                                    sendMessage(inputText, currentAgent, isConnected, serverIp, chatHistories)
                                    inputText = ""
                                }
                            }),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = TextLight,
                                unfocusedTextColor = TextLight,
                                focusedBorderColor = PrimaryIndigo,
                                unfocusedBorderColor = DarkBackground,
                                containerColor = DarkBackground
                            ),
                            modifier = Modifier.weight(1f)
                        )

                        IconButton(
                            onClick = {
                                if (inputText.isNotEmpty()) {
                                    sendMessage(inputText, currentAgent, isConnected, serverIp, chatHistories)
                                    inputText = ""
                                }
                            },
                            colors = IconButtonDefaults.iconButtonColors(containerColor = PrimaryIndigo)
                        ) {
                            Icon(Icons.Default.Send, contentDescription = "Send", tint = Color.White)
                        }
                    }
                }
            }
        ) { paddingValues ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues)
                    .background(DarkBackground)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(DarkSurface)
                        .padding(vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(6.dp, Alignment.CenterHorizontally)
                ) {
                    val agents = listOf("study", "planner", "expense", "content")
                    agents.forEach { agent ->
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(16.dp))
                                .background(if (currentAgent == agent) PrimaryIndigo else DarkBackground)
                                .clickable { currentAgent = agent }
                                .padding(horizontal = 14.dp, vertical = 6.dp)
                        ) {
                            Text(
                                text = agent.replaceFirstChar { it.uppercase() },
                                color = if (currentAgent == agent) Color.White else TextMuted,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }

                Box(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                    OutlinedTextField(
                        value = serverIp,
                        onValueChange = { serverIp = it },
                        label = { Text("Server IP", color = TextMuted) },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = TextLight,
                            unfocusedTextColor = TextLight,
                            focusedBorderColor = PrimaryIndigo,
                            unfocusedBorderColor = DarkSurface
                        ),
                        modifier = Modifier.fillMaxWidth()
                    )
                }

                LazyColumn(
                    state = listState,
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    contentPadding = PaddingValues(vertical = 12.dp)
                ) {
                    items(currentHistory) { message ->
                        ChatBubble(message = message, onPlayTTS = { speak(message.text) })
                    }
                }
            }
        }
    }

    @Composable
    fun ChatBubble(message: ChatMessage, onPlayTTS: () -> Unit) {
        val isUser = message.sender == "user"
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
        ) {
            Box(
                modifier = Modifier
                    .clip(
                        RoundedCornerShape(
                            topStart = 16.dp,
                            topEnd = 16.dp,
                            bottomStart = if (isUser) 16.dp else 4.dp,
                            bottomEnd = if (isUser) 4.dp else 16.dp
                        )
                    )
                    .background(if (isUser) PrimaryIndigo else DarkSurface)
                    .padding(12.dp)
                    .widthIn(max = 280.dp)
            ) {
                Column {
                    if (message.bitmap != null) {
                        androidx.compose.foundation.Image(
                            bitmap = message.bitmap.asImageBitmap(),
                            contentDescription = "User Attachment",
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(160.dp)
                                .clip(RoundedCornerShape(8.dp))
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                    }
                    Text(
                        text = message.text,
                        color = TextLight,
                        fontSize = 14.sp
                    )

                    if (!isUser) {
                        Spacer(modifier = Modifier.height(6.dp))
                        Row(
                            modifier = Modifier
                                .clickable { onPlayTTS() }
                                .padding(vertical = 2.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.PlayArrow, contentDescription = "TTS", tint = SecondaryCyan, modifier = Modifier.size(14.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Speak", color = SecondaryCyan, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }
    }

    private fun sendMessage(
        text: String,
        agent: String,
        isConnected: Boolean,
        serverIp: String,
        chatHistories: MutableMap<String, List<ChatMessage>>
    ) {
        val currentList = chatHistories[agent] ?: emptyList()
        chatHistories[agent] = currentList + ChatMessage(sender = "user", text = text)

        if (isConnected) {
            val payload = when (agent) {
                "study" -> mapOf("content" to text, "is_image" to false)
                "planner" -> {
                    val topics = text.split(",").map { it.trim() }
                    mapOf(
                        "exam_name" to "Upcoming Exam",
                        "exam_date" to "2026-06-25",
                        "syllabus" to topics,
                        "topics_completed" to emptyList<String>()
                    )
                }
                "content" -> mapOf("task" to text, "context" to "No context provided")
                else -> mapOf("content" to text)
            }
            webSocketClient?.send(
                WebSocketRequest(
                    id = UUID.randomUUID().toString(),
                    agent = agent,
                    action = when (agent) {
                        "study" -> "process_material"
                        "planner" -> "generate_schedule"
                        "content" -> "draft_content"
                        else -> "process"
                    },
                    payload = payload
                )
            )
        } else {
            val url = when (agent) {
                "study" -> "http://$serverIp:8000/api/agents/study/process"
                "planner" -> "http://$serverIp:8000/api/agents/planner/schedule"
                "content" -> "http://$serverIp:8000/api/agents/content/draft"
                else -> "http://$serverIp:8000/api/agents/study/process"
            }
            val payload = when (agent) {
                "study" -> mapOf("content" to text, "is_image" to false)
                "planner" -> {
                    val topics = text.split(",").map { it.trim() }
                    mapOf(
                        "exam_name" to "Upcoming Exam",
                        "exam_date" to "2026-06-25",
                        "syllabus" to topics,
                        "topics_completed" to emptyList<String>()
                    )
                }
                "content" -> mapOf("task" to text, "context" to "No context provided")
                else -> mapOf("content" to text)
            }
            makeHttpRequest(
                url = url,
                bodyJson = gson.toJson(payload),
                onSuccess = { res ->
                    val formattedText = formatAgentResponse(agent, res)
                    runOnUiThread {
                        val current = chatHistories[agent] ?: emptyList()
                        chatHistories[agent] = current + ChatMessage(sender = "agent", text = formattedText)
                    }
                },
                onError = { err ->
                    runOnUiThread {
                        val current = chatHistories[agent] ?: emptyList()
                        chatHistories[agent] = current + ChatMessage(sender = "agent", text = "Error: $err")
                    }
                }
            )
        }
    }

    private fun formatAgentResponse(agent: String, jsonResponse: String): String {
        return try {
            when (agent) {
                "study" -> {
                    val resp = gson.fromJson(jsonResponse, StudyResponse::class.java)
                    var out = "📚 SUMMARY:\n${resp.summary}\n\n🏷️ FLASHCARDS:\n"
                    resp.flashcards.forEach { out += "• Q: ${it.q}\n  A: ${it.a}\n" }
                    out += "\n📝 MCQs:\n"
                    resp.mcqs.forEach { out += "• ${it.q}\n  Options: ${it.options.joinToString(", ")}\n  Answer: ${it.answer}\n" }
                    out
                }
                "planner" -> {
                    val resp = gson.fromJson(jsonResponse, PlannerResponse::class.java)
                    var out = "📅 STUDY SCHEDULE FOR: ${resp.exam_name} (Date: ${resp.exam_date})\n\n"
                    resp.schedule.forEach { out += "• Day ${it.day} (${it.date}):\n  Topics: ${it.topics.joinToString(", ")}\n  Hours: ${it.duration_hours}h (${it.study_load} load)\n  Resources: ${it.resources.joinToString(", ")}\n" }
                    if (resp.milestones.isNotEmpty()) {
                        out += "\n🎯 MILESTONES:\n"
                        resp.milestones.forEach { out += "• Day ${it.day}: ${it.milestone}\n" }
                    }
                    out
                }
                "expense" -> {
                    val resp = gson.fromJson(jsonResponse, ExpenseResponse::class.java)
                    "💵 EXPENSE RECEIPT EXTRACTED:\n\n• Amount: $${resp.amount}\n• Merchant: ${resp.merchant}\n• Category: ${resp.category}\n• Date: ${resp.date}\n• Confidence: ${(resp.confidence * 100).toInt()}%"
                }
                "content" -> {
                    val resp = gson.fromJson(jsonResponse, ContentResponse::class.java)
                    "📝 DRAFTED TEXT:\n\n${resp.draft_text}\n\n💡 Suggestions:\n" + resp.suggestions.joinToString("\n") { "• $it" }
                }
                else -> jsonResponse
            }
        } catch (e: Exception) {
            jsonResponse
        }
    }

    private fun makeHttpRequest(url: String, bodyJson: String, onSuccess: (String) -> Unit, onError: (String) -> Unit) {
        val mediaType = "application/json; charset=utf-8".toMediaTypeOrNull()
        val requestBody = bodyJson.toRequestBody(mediaType)
        val request = Request.Builder().url(url).post(requestBody).build()

        CoroutineScope(Dispatchers.IO).launch {
            try {
                httpClient.newCall(request).execute().use { response ->
                    if (response.isSuccessful) {
                        val bodyStr = response.body?.string() ?: ""
                        onSuccess(bodyStr)
                    } else {
                        onError("Server code: ${response.code}")
                    }
                }
            } catch (e: IOException) {
                onError(e.message ?: "Connection failure")
            }
        }
    }

    private fun uriToBase64(uri: Uri, contentResolver: ContentResolver): String? {
        return try {
            val inputStream = contentResolver.openInputStream(uri)
            val bytes = inputStream?.readBytes()
            inputStream?.close()
            bytes?.let { android.util.Base64.encodeToString(it, android.util.Base64.NO_WRAP) }
        } catch (e: Exception) {
            null
        }
    }

    private fun bitmapToBase64(bitmap: Bitmap): String {
        val byteArrayOutputStream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, 90, byteArrayOutputStream)
        val byteArray = byteArrayOutputStream.toByteArray()
        return android.util.Base64.encodeToString(byteArray, android.util.Base64.NO_WRAP)
    }
}
