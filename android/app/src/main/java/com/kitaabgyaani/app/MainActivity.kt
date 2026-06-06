package com.kitaabgyaani.app

import android.app.Activity
import android.app.DatePickerDialog
import java.util.Calendar
import java.util.Locale
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
import androidx.compose.foundation.border
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
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
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
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.core.content.FileProvider
import java.io.File
import kotlinx.coroutines.delay
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.ui.composed
import androidx.compose.ui.graphics.graphicsLayer

fun Modifier.bounceClick(interactionSource: MutableInteractionSource) = composed {
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.96f else 1f,
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioMediumBouncy,
            stiffness = Spring.StiffnessLow
        ),
        label = "bounceScale"
    )
    this.graphicsLayer(scaleX = scale, scaleY = scale)
}

fun Modifier.bounceClickable(onClick: () -> Unit) = composed {
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.96f else 1f,
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioMediumBouncy,
            stiffness = Spring.StiffnessLow
        ),
        label = "bounceScale"
    )
    this
        .graphicsLayer(scaleX = scale, scaleY = scale)
        .clickable(
            interactionSource = interactionSource,
            indication = null
        ) {
            onClick()
        }
}

class MainActivity : ComponentActivity(), TextToSpeech.OnInitListener {

    private lateinit var tts: TextToSpeech
    private var webSocketClient: WebSocketClient? = null
    private val gson = Gson()
    private val httpClient = OkHttpClient()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        tts = TextToSpeech(this, this)

        setContent {
            KitaabGyaaniTheme(darkTheme = true) {
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

    data class ChatSession(
        val id: String,
        val title: String,
        val messages: List<ChatMessage>
    )

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    fun ChatAppScreen() {
        val context = LocalContext.current
        val sharedPrefs = remember { context.getSharedPreferences("KitaabGyaaniPrefs", Context.MODE_PRIVATE) }
        var serverIp by remember { mutableStateOf(sharedPrefs.getString("server_ip", "10.0.2.2") ?: "10.0.2.2") }
        var showSettingsDialog by remember { mutableStateOf(false) }
        var isConnected by remember { mutableStateOf(false) }
        
        // Google Calendar connection and date selection states
        val initCalendar = remember { Calendar.getInstance() }
        val defaultStartStr = remember {
            String.format(Locale.US, "%04d-%02d-%02d",
                initCalendar.get(Calendar.YEAR),
                initCalendar.get(Calendar.MONTH) + 1,
                initCalendar.get(Calendar.DAY_OF_MONTH)
            )
        }
        val defaultEndStr = remember {
            val endCal = Calendar.getInstance()
            endCal.add(Calendar.DAY_OF_MONTH, 7)
            String.format(Locale.US, "%04d-%02d-%02d",
                endCal.get(Calendar.YEAR),
                endCal.get(Calendar.MONTH) + 1,
                endCal.get(Calendar.DAY_OF_MONTH)
            )
        }

        var plannerStartDate by remember { mutableStateOf(defaultStartStr) }
        var plannerEndDate by remember { mutableStateOf(defaultEndStr) }
        var isCalendarConnected by remember { mutableStateOf(false) }
        var isClearingEvents by remember { mutableStateOf(false) }

        fun showDatePicker(ctx: Context, onDateSelected: (String) -> Unit) {
            val cal = Calendar.getInstance()
            DatePickerDialog(
                ctx,
                { _, year, month, day ->
                    val formatted = String.format(Locale.US, "%04d-%02d-%02d", year, month + 1, day)
                    onDateSelected(formatted)
                },
                cal.get(Calendar.YEAR),
                cal.get(Calendar.MONTH),
                cal.get(Calendar.DAY_OF_MONTH)
            ).show()
        }

        var currentAgent by remember { mutableStateOf("study") }
        var inputText by remember { mutableStateOf("") }
        var selectedFileBase64 by remember { mutableStateOf<String?>(null) }
        var selectedFileIsImage by remember { mutableStateOf(false) }
        var selectedFileName by remember { mutableStateOf<String?>(null) }
        var selectedImageBitmap by remember { mutableStateOf<Bitmap?>(null) }
        var cameraPhotoUri by remember { mutableStateOf<Uri?>(null) }

        var isPlayingGame by remember { mutableStateOf(false) }
        var quizQuestions by remember { mutableStateOf<List<GameQuestion>>(emptyList()) }
        var isAgentLoading by remember { mutableStateOf(false) }

        val chatSessions = remember {
            mutableStateMapOf<String, List<ChatSession>>().apply {
                put("study", emptyList())
                put("planner", emptyList())
                put("expense", emptyList())
                put("content", emptyList())
                put("quiz", emptyList())
            }
        }

        val currentSessionIds = remember {
            mutableStateMapOf<String, String?>().apply {
                put("study", null)
                put("planner", null)
                put("expense", null)
                put("content", null)
                put("quiz", null)
            }
        }

        var isGeneratingQuiz by remember { mutableStateOf(false) }

        val launchQuizAction = {
            isGeneratingQuiz = true
            startQuizGame(
                inputText = inputText,
                selectedFileBase64 = selectedFileBase64,
                selectedFileIsImage = selectedFileIsImage,
                serverIp = serverIp,
                currentSessionIds = currentSessionIds,
                onSuccess = { questions ->
                    isGeneratingQuiz = false
                    if (questions.isNotEmpty()) {
                        quizQuestions = questions
                        isPlayingGame = true
                        inputText = ""
                        selectedFileBase64 = null
                        selectedImageBitmap = null
                        selectedFileName = null
                    } else {
                        Toast.makeText(context, "No questions generated", Toast.LENGTH_SHORT).show()
                    }
                }
            )
        }

        val currentSessionId = currentSessionIds[currentAgent]
        val currentHistory = chatSessions[currentAgent]?.find { it.id == currentSessionId }?.messages ?: listOf(
            ChatMessage(
                sender = "agent",
                text = when (currentAgent) {
                    "study" -> "Hello! Send me notes, or take a picture of study material to extract flashcards and summary."
                    "planner" -> "Hello! Send me your exam syllabus topics and target date to generate a study plan."
                    "expense" -> "Hello! Take a photo of a receipt to parse amount, category, and merchant details."
                    "content" -> "Hello! Describe the writing task and context to draft a professional copy."
                    "quiz" -> "Hello! Enter a topic (e.g. Science) or attach a study material to generate a custom quiz and play Space Invaders!"
                    else -> "Hello! How can I help you today?"
                }
            )
        )
        val listState = rememberLazyListState()

        fun parseHistoryJson(res: String) {
            try {
                val type = object : com.google.gson.reflect.TypeToken<Map<String, List<Map<String, Any?>>>>() {}.type
                val rawMap = gson.fromJson<Map<String, List<Map<String, Any?>>>>(res, type) ?: return
                
                rawMap.forEach { (agent, rawSessions) ->
                    val sessionsList = rawSessions.mapNotNull { rawSession ->
                        val id = rawSession["id"] as? String ?: return@mapNotNull null
                        val title = rawSession["title"] as? String ?: "Chat"
                        val rawMessages = rawSession["messages"] as? List<Map<String, Any?>> ?: emptyList()
                        
                        val messagesList = rawMessages.mapNotNull { msg ->
                            val sender = msg["sender"] as? String ?: return@mapNotNull null
                            val text = msg["text"] as? String ?: ""
                            val isImage = msg["is_image"] as? Boolean ?: false
                            val imgBase64 = msg["image_base64"] as? String

                            val bitmap = if (isImage && !imgBase64.isNullOrEmpty()) {
                                try {
                                    val decodedBytes = android.util.Base64.decode(imgBase64, android.util.Base64.DEFAULT)
                                    BitmapFactory.decodeByteArray(decodedBytes, 0, decodedBytes.size)
                                } catch (e: Exception) {
                                    null
                                }
                            } else {
                                null
                            }
                            ChatMessage(sender = sender, text = text, bitmap = bitmap)
                        }
                        ChatSession(id = id, title = title, messages = messagesList)
                    }
                    chatSessions[agent] = sessionsList
                    
                    val currentId = currentSessionIds[agent]
                    val hasCurrent = sessionsList.any { it.id == currentId }
                    if (!hasCurrent && sessionsList.isNotEmpty()) {
                        currentSessionIds[agent] = sessionsList.last().id
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        fun fetchHistory(ip: String) {
            val ipPattern = Regex("""^\d{1,3}(\.\d{1,3}){3}$""")
            if (ipPattern.matches(ip)) {
                makeHttpRequest(
                    url = "http://$ip:8000/api/chat/history",
                    bodyJson = "{}",
                    onSuccess = { res ->
                        runOnUiThread {
                            parseHistoryJson(res)
                        }
                    },
                    onError = { _ -> }
                )
            }
        }

        val webSocketListener = remember {
            object : WebSocketClient.WebSocketListenerInterface {
                override fun onConnected() {
                    isConnected = true
                    runOnUiThread { 
                        Toast.makeText(context, "Connected to KitaabGyaani Server", Toast.LENGTH_SHORT).show() 
                        fetchHistory(serverIp)
                    }
                }

                override fun onDisconnected() {
                    isConnected = false
                    runOnUiThread { 
                        isAgentLoading = false
                        Toast.makeText(context, "Disconnected from Server", Toast.LENGTH_SHORT).show() 
                    }
                }

                override fun onMessageReceived(text: String) {
                    runOnUiThread {
                        isAgentLoading = false
                        try {
                            val wsResponseMap = gson.fromJson<Map<String, Any?>>(text, object : com.google.gson.reflect.TypeToken<Map<String, Any?>>() {}.type)
                            val agentName = (wsResponseMap["agent"] as? String) ?: currentAgent
                            val newSessionId = wsResponseMap["session_id"] as? String
                            if (newSessionId != null) {
                                currentSessionIds[agentName] = newSessionId
                            }
                            fetchHistory(serverIp)
                        } catch (e: Exception) {
                            e.printStackTrace()
                            fetchHistory(serverIp)
                        }
                    }
                }

                override fun onError(error: String) {
                    isConnected = false
                    runOnUiThread { 
                        isAgentLoading = false
                        Toast.makeText(context, "WS Error: $error", Toast.LENGTH_SHORT).show() 
                    }
                }
            }
        }

        LaunchedEffect(serverIp) {
            fetchHistory(serverIp)
            while (true) {
                if (!isConnected) {
                    webSocketClient?.disconnect()
                    webSocketClient = WebSocketClient(webSocketListener)
                    try {
                        webSocketClient?.connect("ws://$serverIp:8000/ws")
                    } catch (e: Exception) {
                        isConnected = false
                    }
                }
                delay(5000)
            }
        }

        LaunchedEffect(currentAgent, isConnected, serverIp) {
            while (true) {
                if (currentAgent == "planner" && isConnected) {
                    try {
                        makeHttpRequest(
                            url = "http://$serverIp:8000/api/calendar/status",
                            bodyJson = "{}",
                            onSuccess = { res ->
                                try {
                                    val statusMap = gson.fromJson<Map<String, Any?>>(res, object : com.google.gson.reflect.TypeToken<Map<String, Any?>>() {}.type)
                                    isCalendarConnected = statusMap["connected"] as? Boolean ?: false
                                } catch (e: Exception) {
                                    isCalendarConnected = false
                                }
                            },
                            onError = { _ ->
                                isCalendarConnected = false
                            }
                        )
                    } catch (e: Exception) {
                        isCalendarConnected = false
                    }
                }
                delay(3000)
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
            contract = ActivityResultContracts.TakePicture()
        ) { _ ->
            cameraPhotoUri?.let { uri ->
                try {
                    val inputStream = context.contentResolver.openInputStream(uri)
                    val capturedBitmap = BitmapFactory.decodeStream(inputStream)
                    inputStream?.close()
                    if (capturedBitmap != null) {
                        selectedImageBitmap = capturedBitmap
                        selectedFileBase64 = bitmapToBase64(capturedBitmap)
                        selectedFileIsImage = true
                        selectedFileName = "camera_capture.jpg"
                    }
                } catch (e: Exception) {
                    Toast.makeText(context, "Failed to load captured image", Toast.LENGTH_SHORT).show()
                }
            }
        }

        fun launchCamera() {
            try {
                val storageDir = context.externalCacheDir ?: context.cacheDir
                val tempFile = File.createTempFile("camera_photo_", ".jpg", storageDir)
                val uri = FileProvider.getUriForFile(
                    context,
                    context.packageName + ".fileprovider",
                    tempFile
                )
                cameraPhotoUri = uri
                cameraLauncher.launch(uri)
            } catch (e: Exception) {
                Toast.makeText(context, "Failed to create temp file: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }

        val cameraPermissionLauncher = rememberLauncherForActivityResult(
            contract = ActivityResultContracts.RequestPermission()
        ) { isGranted ->
            if (isGranted) {
                launchCamera()
            } else {
                Toast.makeText(context, "Camera permission denied", Toast.LENGTH_SHORT).show()
            }
        }

        val filePickerLauncher = rememberLauncherForActivityResult(
            contract = ActivityResultContracts.GetContent()
        ) { uri: Uri? ->
            uri?.let {
                val contentResolver = context.contentResolver
                val base64 = uriToBase64(it, contentResolver)
                if (base64 != null) {
                    selectedImageBitmap = null
                    selectedFileBase64 = base64
                    selectedFileIsImage = contentResolver.getType(it)?.startsWith("image/") == true
                    selectedFileName = getFileName(it, contentResolver) ?: "document"
                    if (selectedFileIsImage) {
                        try {
                            val inputStream = contentResolver.openInputStream(it)
                            selectedImageBitmap = BitmapFactory.decodeStream(inputStream)
                            inputStream?.close()
                        } catch (e: Exception) {}
                    }
                }
            }
        }

        val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
        val scope = rememberCoroutineScope()

        AnimatedContent(
            targetState = isPlayingGame,
            transitionSpec = {
                fadeIn(animationSpec = tween(300)) togetherWith fadeOut(animationSpec = tween(300))
            },
            label = "screen_transition"
        ) { playing ->
            if (playing) {
                GameScreen(
                    questions = quizQuestions,
                    serverIp = serverIp,
                    onBackToChat = { isPlayingGame = false },
                    onPlayAgain = {
                        isPlayingGame = false
                        launchQuizAction()
                    }
                )
            } else {
            ModalNavigationDrawer(
                drawerState = drawerState,
            drawerContent = {
                ModalDrawerSheet(
                    drawerContainerColor = DarkSurfaceRaised,
                    modifier = Modifier.width(280.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp)
                    ) {
                        Text(
                            text = "KitaabGyaani Chat",
                            fontWeight = FontWeight.Bold,
                            fontSize = 20.sp,
                            color = TextLight,
                            modifier = Modifier.padding(bottom = 16.dp)
                        )
                        
                        val newChatInteraction = remember { MutableInteractionSource() }
                        Button(
                            onClick = {
                                currentSessionIds[currentAgent] = null
                                scope.launch { drawerState.close() }
                            },
                            interactionSource = newChatInteraction,
                            colors = ButtonDefaults.buttonColors(
                                containerColor = PrimaryIndigo,
                                contentColor = MaterialTheme.colorScheme.onPrimary
                            ),
                            modifier = Modifier
                                .fillMaxWidth()
                                .bounceClick(newChatInteraction),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Icon(Icons.Default.Add, contentDescription = "New Chat")
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("New Chat", fontWeight = FontWeight.SemiBold)
                        }
                        
                        Spacer(modifier = Modifier.height(24.dp))
                        
                        Text(
                            text = "Previous Chats",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 14.sp,
                            color = TextMuted,
                            modifier = Modifier.padding(bottom = 8.dp)
                        )
                        
                        val sessions = chatSessions[currentAgent] ?: emptyList()
                        if (sessions.isEmpty()) {
                            Box(
                                modifier = Modifier
                                    .weight(1f)
                                    .fillMaxWidth(),
                                contentAlignment = Alignment.Center
                            ) {
                                Text("No previous chats", color = TextMuted, fontSize = 13.sp)
                            }
                        } else {
                            LazyColumn(
                                modifier = Modifier.weight(1f),
                                verticalArrangement = Arrangement.spacedBy(4.dp)
                            ) {
                                items(sessions.reversed()) { session ->
                                    val isSelected = currentSessionId == session.id
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(if (isSelected) PrimarySoft else Color.Transparent)
                                            .clickable {
                                                currentSessionIds[currentAgent] = session.id
                                                scope.launch { drawerState.close() }
                                            }
                                            .padding(horizontal = 12.dp, vertical = 10.dp)
                                    ) {
                                        Text(
                                            text = session.title,
                                            color = if (isSelected) TextLight else TextMuted,
                                            fontSize = 14.sp,
                                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                            maxLines = 1
                                        )
                                    }
                                }
                            }
                        }
                        
                        Spacer(modifier = Modifier.height(16.dp))
                        
                        val clearHistoryInteraction = remember { MutableInteractionSource() }
                        Button(
                            onClick = {
                                makeHttpRequest(
                                    url = "http://$serverIp:8000/api/chat/clear",
                                    bodyJson = "{}",
                                    onSuccess = {
                                        runOnUiThread {
                                            chatSessions.clear()
                                            currentSessionIds[currentAgent] = null
                                            fetchHistory(serverIp)
                                            Toast.makeText(context, "History cleared", Toast.LENGTH_SHORT).show()
                                        }
                                    },
                                    onError = { err ->
                                        runOnUiThread {
                                            Toast.makeText(context, "Error: $err", Toast.LENGTH_SHORT).show()
                                        }
                                    }
                                )
                                scope.launch { drawerState.close() }
                            },
                            interactionSource = clearHistoryInteraction,
                            colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent),
                            modifier = Modifier
                                .fillMaxWidth()
                                .bounceClick(clearHistoryInteraction)
                        ) {
                            Icon(Icons.Default.Delete, contentDescription = "Clear History", tint = AccentError)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Clear All Chats", color = AccentError, fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            }
        ) {
            Scaffold(
                topBar = {
                    TopAppBar(
                        navigationIcon = {
                            IconButton(onClick = { scope.launch { drawerState.open() } }) {
                                Icon(Icons.Default.Menu, contentDescription = "Open Side Drawer", tint = TextLight)
                            }
                        },
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
                                            .background(if (isConnected) AccentEmerald else AccentError)
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
                        colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkSurfaceRaised),
                        actions = {
                            IconButton(onClick = { filePickerLauncher.launch("*/*") }) {
                                Icon(Icons.Default.AttachFile, contentDescription = "Upload Document", tint = TextLight)
                            }
                            IconButton(onClick = { showSettingsDialog = true }) {
                                Icon(Icons.Default.Settings, contentDescription = "Settings", tint = TextLight)
                            }
                        }
                    )

                    if (showSettingsDialog) {
                        AlertDialog(
                            onDismissRequest = { showSettingsDialog = false },
                            title = { Text("Settings", color = TextLight, fontWeight = FontWeight.Bold) },
                            text = {
                                Column {
                                    Text("Configure Backend Server IP", color = TextMuted, fontSize = 12.sp)
                                    Spacer(modifier = Modifier.height(12.dp))
                                    OutlinedTextField(
                                        value = serverIp,
                                        onValueChange = { 
                                            serverIp = it 
                                            sharedPrefs.edit().putString("server_ip", it).apply()
                                        },
                                        label = { Text("Server IP", color = TextMuted) },
                                        colors = OutlinedTextFieldDefaults.colors(
                                            focusedTextColor = TextLight,
                                            unfocusedTextColor = TextLight,
                                            focusedBorderColor = PrimaryIndigo,
                                            unfocusedBorderColor = DarkOutlineSoft,
                                            focusedContainerColor = DarkSurfaceField,
                                            unfocusedContainerColor = DarkSurfaceField,
                                            cursorColor = PrimaryIndigo
                                        ),
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                }
                            },
                            confirmButton = {
                                TextButton(onClick = { showSettingsDialog = false }) {
                                    Text("Done", color = PrimaryIndigo, fontWeight = FontWeight.SemiBold)
                                }
                            },
                            containerColor = DarkSurfaceCard
                        )
                    }
                },
                bottomBar = {
                    Column(
                        modifier = Modifier
                            .background(DarkSurfaceRaised)
                            .padding(horizontal = 8.dp, vertical = 8.dp)
                            .navigationBarsPadding()
                            .imePadding()
                    ) {
                        if (selectedFileBase64 != null) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(bottom = 8.dp)
                                    .background(DarkSurfaceField, shape = RoundedCornerShape(12.dp))
                                    .padding(8.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                if (selectedImageBitmap != null) {
                                    androidx.compose.foundation.Image(
                                        bitmap = selectedImageBitmap!!.asImageBitmap(),
                                        contentDescription = "Attachment Preview",
                                        modifier = Modifier
                                            .size(48.dp)
                                            .clip(RoundedCornerShape(8.dp))
                                    )
                                } else {
                                    Box(
                                        modifier = Modifier
                                            .size(48.dp)
                                            .background(PrimarySoft, shape = RoundedCornerShape(8.dp)),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Icon(
                                            imageVector = if (selectedFileName?.endsWith(".pdf", ignoreCase = true) == true) Icons.Default.Description else Icons.Default.Share,
                                            contentDescription = "File Icon",
                                            tint = PrimaryIndigo
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.width(12.dp))

                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = selectedFileName ?: "Attached File",
                                        color = TextLight,
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Text(
                                        text = if (selectedFileIsImage) "Ready to analyze image" else "Ready to analyze document",
                                        color = TextMuted,
                                        fontSize = 11.sp
                                    )
                                }

                                IconButton(onClick = {
                                    selectedFileBase64 = null
                                    selectedImageBitmap = null
                                    selectedFileName = null
                                }) {
                                    Icon(Icons.Default.Close, contentDescription = "Clear Attachment", tint = AccentError)
                                }
                            }
                        }

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            val cameraInteraction = remember { MutableInteractionSource() }
                            IconButton(
                                onClick = {
                                    val hasPermission = androidx.core.content.ContextCompat.checkSelfPermission(
                                        context, android.Manifest.permission.CAMERA
                                    ) == android.content.pm.PackageManager.PERMISSION_GRANTED
                                    if (hasPermission) {
                                        launchCamera()
                                    } else {
                                        cameraPermissionLauncher.launch(android.Manifest.permission.CAMERA)
                                    }
                                },
                                interactionSource = cameraInteraction,
                                colors = IconButtonDefaults.iconButtonColors(containerColor = DarkSurfaceField),
                                modifier = Modifier.bounceClick(cameraInteraction)
                            ) {
                                Icon(Icons.Default.Add, contentDescription = "Camera", tint = SecondaryCyan)
                            }

                            val micInteraction = remember { MutableInteractionSource() }
                            IconButton(
                                onClick = {
                                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                                        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                        putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                                    }
                                    speechLauncher.launch(intent)
                                },
                                interactionSource = micInteraction,
                                colors = IconButtonDefaults.iconButtonColors(containerColor = DarkSurfaceField),
                                modifier = Modifier.bounceClick(micInteraction)
                            ) {
                                Icon(Icons.Default.Mic, contentDescription = "Voice Input", tint = SecondaryCyan)
                            }

                            OutlinedTextField(
                                value = inputText,
                                onValueChange = { inputText = it },
                                placeholder = { Text("Ask anything to ${currentAgent}...", color = TextMuted) },
                                maxLines = 3,
                                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                                keyboardActions = KeyboardActions(onSend = {
                                    if (inputText.isNotEmpty() || selectedFileBase64 != null) {
                                        if (currentAgent == "quiz") {
                                            launchQuizAction()
                                        } else {
                                            sendMessage(
                                                text = inputText,
                                                agent = currentAgent,
                                                isConnected = isConnected,
                                                serverIp = serverIp,
                                                chatSessions = chatSessions,
                                                currentSessionIds = currentSessionIds,
                                                fileBase64 = selectedFileBase64,
                                                isImage = selectedFileIsImage,
                                                imageBitmap = selectedImageBitmap,
                                                plannerStartDate = plannerStartDate,
                                                plannerEndDate = plannerEndDate,
                                                onClearAttachment = {
                                                    selectedFileBase64 = null
                                                    selectedImageBitmap = null
                                                    selectedFileName = null
                                                },
                                                onResponseReceived = {
                                                    fetchHistory(serverIp)
                                                },
                                                onStartLoading = { isAgentLoading = true },
                                                onEndLoading = { isAgentLoading = false }
                                            )
                                            inputText = ""
                                        }
                                    }
                                }),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = TextLight,
                                    unfocusedTextColor = TextLight,
                                    focusedBorderColor = PrimaryIndigo,
                                    unfocusedBorderColor = DarkOutlineSoft,
                                    focusedContainerColor = DarkSurfaceField,
                                    unfocusedContainerColor = DarkSurfaceField,
                                    cursorColor = PrimaryIndigo
                                ),
                                modifier = Modifier.weight(1f)
                            )

                             val sendInteraction = remember { MutableInteractionSource() }
                             IconButton(
                                onClick = {
                                    if (inputText.isNotEmpty() || selectedFileBase64 != null) {
                                        if (currentAgent == "quiz") {
                                            launchQuizAction()
                                        } else {
                                            sendMessage(
                                                text = inputText,
                                                agent = currentAgent,
                                                isConnected = isConnected,
                                                serverIp = serverIp,
                                                chatSessions = chatSessions,
                                                currentSessionIds = currentSessionIds,
                                                fileBase64 = selectedFileBase64,
                                                isImage = selectedFileIsImage,
                                                imageBitmap = selectedImageBitmap,
                                                plannerStartDate = plannerStartDate,
                                                plannerEndDate = plannerEndDate,
                                                onClearAttachment = {
                                                    selectedFileBase64 = null
                                                    selectedImageBitmap = null
                                                    selectedFileName = null
                                                },
                                                onResponseReceived = {
                                                    fetchHistory(serverIp)
                                                },
                                                onStartLoading = { isAgentLoading = true },
                                                onEndLoading = { isAgentLoading = false }
                                            )
                                            inputText = ""
                                        }
                                    }
                                },
                                interactionSource = sendInteraction,
                                colors = IconButtonDefaults.iconButtonColors(
                                    containerColor = PrimaryIndigo,
                                    contentColor = MaterialTheme.colorScheme.onPrimary
                                ),
                                modifier = Modifier.bounceClick(sendInteraction)
                            ) {
                                Icon(Icons.Default.Send, contentDescription = "Send")
                            }
                        }
                    }
                }
            ) { paddingValues ->
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues)
                        .background(MaterialTheme.colorScheme.background)
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(DarkSurfaceRaised)
                            .padding(vertical = 8.dp, horizontal = 12.dp)
                    ) {
                        val agents = listOf("study", "planner", "expense", "content", "quiz")
                        val selectedIndex = agents.indexOf(currentAgent).coerceAtLeast(0)
                        
                        BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
                            val tabWidth = maxWidth / agents.size
                            val indicatorOffset by animateDpAsState(
                                targetValue = tabWidth * selectedIndex,
                                animationSpec = spring(
                                    dampingRatio = Spring.DampingRatioNoBouncy,
                                    stiffness = Spring.StiffnessMediumLow
                                ),
                                label = "tabIndicatorOffset"
                            )
                            
                            Box(
                                modifier = Modifier
                                    .offset(x = indicatorOffset)
                                    .width(tabWidth)
                                    .height(32.dp)
                                    .background(PrimarySoft, shape = RoundedCornerShape(8.dp))
                            )
                            
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                agents.forEach { agent ->
                                    val isSelected = currentAgent == agent
                                    val textColor by animateColorAsState(
                                        targetValue = if (isSelected) PrimaryIndigo else TextMuted,
                                        animationSpec = tween(durationMillis = 200),
                                        label = "tabTextColor"
                                    )
                                    
                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .height(32.dp)
                                            .bounceClickable {
                                                currentAgent = agent
                                            },
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            text = agent.replaceFirstChar { it.uppercase() },
                                            color = textColor,
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Bold
                                        )
                                    }
                                }
                            }
                        }
                    }

                    if (currentAgent == "quiz") {
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .fillMaxWidth()
                                .padding(24.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(90.dp)
                                    .background(PrimarySoft, shape = RoundedCornerShape(20.dp)),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Default.PlayArrow,
                                    contentDescription = "Quiz Icon",
                                    tint = PrimaryIndigo,
                                    modifier = Modifier.size(50.dp)
                                )
                            }
                            
                            Spacer(modifier = Modifier.height(24.dp))
                            
                            Text(
                                text = "Space Invaders Quiz",
                                color = TextLight,
                                fontSize = 24.sp,
                                fontWeight = FontWeight.Bold
                            )
                            
                            Spacer(modifier = Modifier.height(8.dp))
                            
                            Text(
                                text = "Spawn dynamic MCQs from your custom topic or notes. Control your ship to shoot down correct answers!",
                                color = TextMuted,
                                fontSize = 13.sp,
                                textAlign = TextAlign.Center,
                                modifier = Modifier.padding(horizontal = 16.dp)
                            )
                            
                            Spacer(modifier = Modifier.height(32.dp))
                            
                            if (isGeneratingQuiz) {
                                CircularProgressIndicator(color = SecondaryCyan, modifier = Modifier.size(40.dp))
                                Spacer(modifier = Modifier.height(16.dp))
                                Text(
                                    text = "Analyzing material & spawning meteors...",
                                    color = SecondaryCyan,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Medium
                                )
                            } else {
                                val isInputReady = inputText.trim().isNotEmpty() || selectedFileBase64 != null
                                if (isInputReady) {
                                    val launchQuizInteraction = remember { MutableInteractionSource() }
                                    Button(
                                        onClick = { launchQuizAction() },
                                        interactionSource = launchQuizInteraction,
                                        colors = ButtonDefaults.buttonColors(
                                            containerColor = PrimaryIndigo,
                                            contentColor = MaterialTheme.colorScheme.onPrimary
                                        ),
                                        shape = RoundedCornerShape(14.dp),
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .height(56.dp)
                                            .bounceClick(launchQuizInteraction)
                                    ) {
                                        Icon(Icons.Default.PlayArrow, contentDescription = "Play Icon")
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Text("LAUNCH QUIZ GAME", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                                    }
                                } else {
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .background(DarkSurfaceCard, shape = RoundedCornerShape(12.dp))
                                            .padding(16.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            text = "💡 Type a topic or attach a file below to start the quiz!",
                                            color = TextMuted,
                                            fontSize = 13.sp,
                                            textAlign = TextAlign.Center
                                        )
                                    }
                                }
                            }
                        }
                    } else {
                        if (currentAgent == "planner") {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 16.dp, vertical = 8.dp)
                                    .background(DarkSurfaceCard, shape = RoundedCornerShape(12.dp))
                                    .border(
                                        1.dp,
                                        if (isCalendarConnected) AccentEmerald.copy(alpha = 0.45f) else AccentWarning.copy(alpha = 0.45f),
                                        shape = RoundedCornerShape(12.dp)
                                    )
                                    .padding(12.dp)
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Box(
                                            modifier = Modifier
                                                .size(8.dp)
                                                .clip(CircleShape)
                                                .background(if (isCalendarConnected) AccentEmerald else AccentWarning)
                                        )
                                        Spacer(modifier = Modifier.width(6.dp))
                                        Text(
                                            text = if (isCalendarConnected) "Google Calendar Linked" else "Google Calendar Not Connected",
                                            color = TextLight,
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Bold
                                        )
                                    }
                                    if (!isCalendarConnected) {
                                        Text(
                                            text = "LINK",
                                            color = AccentWarning,
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Bold,
                                            modifier = Modifier
                                                .clickable {
                                                    // Open Google OAuth flow on backend using the nip.io wildcard domain
                                                    val loginUrl = "http://$serverIp.nip.io:8000/login"
                                                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(loginUrl))
                                                    context.startActivity(intent)
                                                }
                                                .padding(horizontal = 6.dp, vertical = 2.dp)
                                        )
                                    } else {
                                        if (isClearingEvents) {
                                            CircularProgressIndicator(
                                                color = AccentError,
                                                modifier = Modifier.size(16.dp),
                                                strokeWidth = 2.dp
                                            )
                                        } else {
                                            Text(
                                                text = "CLEAR EVENTS",
                                                color = AccentError,
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.Bold,
                                                modifier = Modifier
                                                    .clickable {
                                                        isClearingEvents = true
                                                        makeHttpRequest(
                                                            url = "http://$serverIp:8000/api/calendar/clear-events",
                                                            bodyJson = "{}",
                                                            onSuccess = { res ->
                                                                (context as? Activity)?.runOnUiThread {
                                                                    isClearingEvents = false
                                                                    try {
                                                                        val responseMap = gson.fromJson<Map<String, Any?>>(res, object : com.google.gson.reflect.TypeToken<Map<String, Any?>>() {}.type)
                                                                        val deletedCount = (responseMap["deleted_count"] as? Number)?.toInt() ?: 0
                                                                        Toast.makeText(context, "Cleared $deletedCount study events!", Toast.LENGTH_LONG).show()
                                                                    } catch (e: Exception) {
                                                                        Toast.makeText(context, "Cleared study events!", Toast.LENGTH_LONG).show()
                                                                    }
                                                                }
                                                            },
                                                            onError = { err ->
                                                                (context as? Activity)?.runOnUiThread {
                                                                    isClearingEvents = false
                                                                    Toast.makeText(context, "Error: $err", Toast.LENGTH_LONG).show()
                                                                }
                                                            }
                                                        )
                                                    }
                                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                                            )
                                        }
                                    }
                                }
                                
                                Spacer(modifier = Modifier.height(10.dp))
                                
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .background(DarkSurfaceField, shape = RoundedCornerShape(8.dp))
                                            .clickable {
                                                showDatePicker(context) { date -> plannerStartDate = date }
                                            }
                                            .padding(8.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            Text("START DATE", color = TextMuted, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                                            Spacer(modifier = Modifier.height(2.dp))
                                            Text(
                                                text = plannerStartDate,
                                                color = TextLight,
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.SemiBold
                                            )
                                        }
                                    }
                                    
                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .background(DarkSurfaceField, shape = RoundedCornerShape(8.dp))
                                            .clickable {
                                                showDatePicker(context) { date -> plannerEndDate = date }
                                            }
                                            .padding(8.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            Text("END DATE / EXAM", color = TextMuted, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                                            Spacer(modifier = Modifier.height(2.dp))
                                            Text(
                                                text = plannerEndDate,
                                                color = TextLight,
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.SemiBold
                                            )
                                        }
                                    }
                                }
                            }
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
                                ChatBubble(
                                    message = message,
                                    onPlayTTS = { speak(message.text) },
                                    onConnectCalendar = {
                                        val loginUrl = "http://$serverIp.nip.io:8000/login"
                                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(loginUrl))
                                        context.startActivity(intent)
                                    }
                                )
                            }
                            if (isAgentLoading) {
                                item {
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(vertical = 4.dp),
                                        contentAlignment = Alignment.CenterStart
                                    ) {
                                        Row(
                                            verticalAlignment = Alignment.CenterVertically,
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 4.dp, bottomEnd = 16.dp))
                                                .background(DarkSurfaceCard)
                                                .padding(horizontal = 14.dp, vertical = 12.dp)
                                        ) {
                                            CircularProgressIndicator(
                                                color = SecondaryCyan,
                                                modifier = Modifier.size(16.dp),
                                                strokeWidth = 2.dp
                                            )
                                            Spacer(modifier = Modifier.width(8.dp))
                                            Text(
                                                text = "${currentAgent.replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.getDefault()) else it.toString() }} Agent is thinking...",
                                                color = TextMuted,
                                                fontSize = 13.sp,
                                                fontWeight = FontWeight.Medium
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
}

    @Composable
    fun ChatBubble(
        message: ChatMessage,
        onPlayTTS: () -> Unit,
        onConnectCalendar: () -> Unit = {}
    ) {
        val isUser = message.sender == "user"
        val animAlpha = remember { Animatable(0f) }
        val animOffsetY = remember { Animatable(16f) }
        
        LaunchedEffect(message.id) {
            launch {
                animAlpha.animateTo(
                    targetValue = 1f,
                    animationSpec = tween(durationMillis = 300, easing = FastOutSlowInEasing)
                )
            }
            launch {
                animOffsetY.animateTo(
                    targetValue = 0f,
                    animationSpec = tween(durationMillis = 300, easing = FastOutSlowInEasing)
                )
            }
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .graphicsLayer(
                    alpha = animAlpha.value,
                    translationY = animOffsetY.value
                ),
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
                    .background(if (isUser) PrimarySoft else DarkSurfaceCard)
                    .padding(horizontal = 14.dp, vertical = 12.dp)
                    .widthIn(max = 300.dp)
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

                    val hasConnectButton = message.text.contains("[Connect Google Calendar]")
                    val cleanedText = if (hasConnectButton) {
                        message.text.substringBefore("[Connect Google Calendar]").trim()
                    } else {
                        message.text
                    }

                    val parsedText = parseMarkdownToAnnotatedString(cleanedText, isUser)
                    Text(
                        text = parsedText,
                        color = if (isUser) Color(0xFFEADAB3) else TextLight,
                        fontSize = 14.sp,
                        lineHeight = 21.sp
                    )

                    if (hasConnectButton) {
                        Spacer(modifier = Modifier.height(8.dp))
                        val connectCalendarInteraction = remember { MutableInteractionSource() }
                        Button(
                            onClick = { onConnectCalendar() },
                            interactionSource = connectCalendarInteraction,
                            colors = ButtonDefaults.buttonColors(
                                containerColor = AccentWarning,
                                contentColor = Color(0xFF2B2110)
                            ),
                            shape = RoundedCornerShape(8.dp),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .bounceClick(connectCalendarInteraction)
                        ) {
                            Text(
                                text = "Connect Google Calendar",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }

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
        chatSessions: MutableMap<String, List<ChatSession>>,
        currentSessionIds: MutableMap<String, String?>,
        fileBase64: String? = null,
        isImage: Boolean = false,
        imageBitmap: Bitmap? = null,
        plannerStartDate: String = "",
        plannerEndDate: String = "",
        onClearAttachment: () -> Unit = {},
        onResponseReceived: () -> Unit = {},
        onStartLoading: () -> Unit = {},
        onEndLoading: () -> Unit = {}
    ) {
        val currentId = currentSessionIds[agent]
        val userMsgText = if (text.isNotEmpty()) text else if (fileBase64 != null) "Attached document for analysis" else ""
        if (userMsgText.isEmpty() && fileBase64 == null) return

        onStartLoading()

        val localUserMsg = ChatMessage(sender = "user", text = userMsgText, bitmap = imageBitmap)
        
        val sessionsList = chatSessions[agent] ?: emptyList()
        val activeSession = sessionsList.find { it.id == currentId }
        if (activeSession != null) {
            val updatedMessages = activeSession.messages + localUserMsg
            val updatedSession = activeSession.copy(messages = updatedMessages)
            chatSessions[agent] = sessionsList.map { if (it.id == activeSession.id) updatedSession else it }
        } else {
            val tempSessionId = "temp_${UUID.randomUUID()}"
            val tempSession = ChatSession(
                id = tempSessionId,
                title = if (userMsgText.length > 25) userMsgText.substring(0, 25) + "..." else userMsgText,
                messages = listOf(localUserMsg)
            )
            chatSessions[agent] = sessionsList + tempSession
            currentSessionIds[agent] = tempSessionId
        }

        if (isConnected) {
            val payload = (if (fileBase64 != null) {
                if (agent == "expense") {
                    mapOf("image_base64" to fileBase64, "prompt_text" to text)
                } else {
                    mapOf("file_base64" to fileBase64, "is_image" to isImage, "prompt_text" to text)
                }
            } else {
                when (agent) {
                    "study" -> mapOf("content" to text, "is_image" to false)
                    "planner" -> {
                        val topics = text.split(",").map { it.trim() }
                        mapOf(
                            "exam_name" to "Planner Schedule / Exam",
                            "exam_date" to plannerEndDate,
                            "start_date" to plannerStartDate,
                            "syllabus" to topics,
                            "topics_completed" to emptyList<String>()
                        )
                    }
                    "content" -> mapOf("task" to text, "context" to "No context provided")
                    else -> mapOf("content" to text)
                }
            }).toMutableMap()

            val sessionToSend = if (currentId != null && !currentId.startsWith("temp_")) currentId else null
            sessionToSend?.let { payload["session_id"] = it }

            webSocketClient?.send(
                WebSocketRequest(
                    id = UUID.randomUUID().toString(),
                    agent = agent,
                    action = if (fileBase64 != null) {
                        if (agent == "expense") "process_receipt" else "process_material"
                    } else {
                        when (agent) {
                            "study" -> "process_material"
                            "planner" -> "generate_schedule"
                            "content" -> "draft_content"
                            else -> "process"
                        }
                    },
                    payload = payload
                )
            )
        } else {
            val url = when (agent) {
                "study" -> "http://$serverIp:8000/api/agents/study/process"
                "planner" -> "http://$serverIp:8000/api/agents/planner/schedule"
                "expense" -> "http://$serverIp:8000/api/agents/expense/process"
                "content" -> "http://$serverIp:8000/api/agents/content/draft"
                else -> "http://$serverIp:8000/api/agents/study/process"
            }

            val payload = (if (fileBase64 != null) {
                if (agent == "expense") {
                    mapOf("image_base64" to fileBase64, "prompt_text" to text)
                } else {
                    mapOf("content" to fileBase64, "is_image" to isImage, "prompt_text" to text)
                }
            } else {
                when (agent) {
                    "study" -> mapOf("content" to text, "is_image" to false)
                    "planner" -> {
                        val topics = text.split(",").map { it.trim() }
                        mapOf(
                            "exam_name" to "Planner Schedule / Exam",
                            "exam_date" to plannerEndDate,
                            "start_date" to plannerStartDate,
                            "syllabus" to topics,
                            "topics_completed" to emptyList<String>()
                        )
                    }
                    "content" -> mapOf("task" to text, "context" to "No context provided")
                    else -> mapOf("content" to text)
                }
            }).toMutableMap()

            val sessionToSend = if (currentId != null && !currentId.startsWith("temp_")) currentId else null
            sessionToSend?.let { payload["session_id"] = it }

            makeHttpRequest(
                url = url,
                bodyJson = gson.toJson(payload),
                onSuccess = { res ->
                    val resMap = try {
                        gson.fromJson<Map<String, Any?>>(res, object : com.google.gson.reflect.TypeToken<Map<String, Any?>>() {}.type)
                    } catch(e: Exception) { null }
                    val newSessionId = resMap?.get("session_id") as? String
                    runOnUiThread {
                        if (newSessionId != null) {
                            currentSessionIds[agent] = newSessionId
                        }
                        onEndLoading()
                        onResponseReceived()
                    }
                },
                onError = { err ->
                    runOnUiThread {
                        onEndLoading()
                        Toast.makeText(this, "Error: $err", Toast.LENGTH_SHORT).show()
                    }
                }
            )
        }

        onClearAttachment()
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
        try {
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
                } catch (e: Exception) {
                    onError(e.message ?: "Connection failure")
                }
            }
        } catch (e: Exception) {
            // Malformed URL or other setup error — silently ignore
            onError(e.message ?: "Invalid request")
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
        val maxDimension = 1024
        val width = bitmap.width
        val height = bitmap.height
        val scaledBitmap = if (width > maxDimension || height > maxDimension) {
            val newWidth: Int
            val newHeight: Int
            if (width > height) {
                newWidth = maxDimension
                newHeight = (height * (maxDimension.toFloat() / width.toFloat())).toInt()
            } else {
                newHeight = maxDimension
                newWidth = (width * (maxDimension.toFloat() / height.toFloat())).toInt()
            }
            Bitmap.createScaledBitmap(bitmap, newWidth, newHeight, true)
        } else {
            bitmap
        }
        val byteArrayOutputStream = ByteArrayOutputStream()
        scaledBitmap.compress(Bitmap.CompressFormat.JPEG, 80, byteArrayOutputStream)
        val byteArray = byteArrayOutputStream.toByteArray()
        return android.util.Base64.encodeToString(byteArray, android.util.Base64.NO_WRAP)
    }

    private fun getFileName(uri: Uri, contentResolver: ContentResolver): String? {
        var result: String? = null
        if (uri.scheme == "content") {
            val cursor = contentResolver.query(uri, null, null, null, null)
            try {
                if (cursor != null && cursor.moveToFirst()) {
                    val index = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                    if (index >= 0) {
                        result = cursor.getString(index)
                    }
                }
            } finally {
                cursor?.close()
            }
        }
        if (result == null) {
            result = uri.path
            val cut = result?.lastIndexOf('/') ?: -1
            if (cut != -1) {
                result = result?.substring(cut + 1)
            }
        }
        return result
    }

    private fun startQuizGame(
        inputText: String,
        selectedFileBase64: String?,
        selectedFileIsImage: Boolean,
        serverIp: String,
        currentSessionIds: MutableMap<String, String?>,
        onSuccess: (List<GameQuestion>) -> Unit
    ) {
        val payload = mutableMapOf<String, Any?>()
        if (!selectedFileBase64.isNullOrEmpty()) {
            payload["content"] = selectedFileBase64
            payload["is_image"] = selectedFileIsImage
        }
        if (inputText.isNotEmpty()) {
            payload["topic"] = inputText
        }
        val currentId = currentSessionIds["quiz"]
        if (currentId != null && !currentId.startsWith("temp_")) {
            payload["session_id"] = currentId
        }

        val url = "http://$serverIp:8000/api/agents/quiz/generate"
        makeHttpRequest(
            url = url,
            bodyJson = gson.toJson(payload),
            onSuccess = { res ->
                try {
                    val resMap = gson.fromJson<Map<String, Any?>>(res, object : com.google.gson.reflect.TypeToken<Map<String, Any?>>() {}.type)
                    val newSessionId = resMap?.get("session_id") as? String
                    runOnUiThread {
                        if (newSessionId != null) {
                            currentSessionIds["quiz"] = newSessionId
                        }
                    }
                    val quizListRaw = resMap?.get("quiz") as? List<Map<String, Any?>>
                    if (quizListRaw != null) {
                        val questionsList = quizListRaw.mapNotNull { qMap ->
                            val q = qMap["question"] as? String ?: return@mapNotNull null
                            val opts = qMap["options"] as? List<String> ?: return@mapNotNull null
                            val correct = (qMap["correctIndex"] as? Number)?.toInt() ?: 0
                            GameQuestion(q, opts, correct)
                        }
                        runOnUiThread {
                            onSuccess(questionsList)
                        }
                    } else {
                        runOnUiThread {
                            Toast.makeText(this, "Failed to parse quiz response", Toast.LENGTH_SHORT).show()
                        }
                    }
                } catch (e: Exception) {
                    runOnUiThread {
                        Toast.makeText(this, "Quiz generation error: ${e.message}", Toast.LENGTH_SHORT).show()
                    }
                }
            },
            onError = { err ->
                runOnUiThread {
                    Toast.makeText(this, "Connection error: $err", Toast.LENGTH_SHORT).show()
                }
            }
        )
    }
    private fun parseMarkdownToAnnotatedString(text: String, isUser: Boolean): AnnotatedString {
        return buildAnnotatedString {
            var cursor = 0
            val regex = Regex("""(\*\*|`|\*)(.*?)\1""")
            val matches = regex.findAll(text)
            
            for (match in matches) {
                val start = match.range.first
                val end = match.range.last + 1
                val delimiter = match.groupValues[1]
                val content = match.groupValues[2]
                
                if (start > cursor) {
                    append(text.substring(cursor, start))
                }
                
                when (delimiter) {
                    "**" -> {
                        withStyle(style = SpanStyle(fontWeight = FontWeight.Bold, color = if (isUser) Color(0xFFFFF4D4) else Color.White)) {
                            append(content)
                        }
                    }
                    "*" -> {
                        withStyle(style = SpanStyle(fontStyle = FontStyle.Italic)) {
                            append(content)
                        }
                    }
                    "`" -> {
                        withStyle(style = SpanStyle(
                            fontFamily = FontFamily.Monospace, 
                            background = if (isUser) Color(0x33000000) else Color(0x33FFFFFF), 
                            color = Color(0xFF22D3EE)
                        )) {
                            append(content)
                        }
                    }
                }
                cursor = end
            }
            
            if (cursor < text.length) {
                append(text.substring(cursor))
            }
        }
    }
}

data class GameQuestion(
    val question: String,
    val options: List<String>,
    val correctIndex: Int
)

data class Meteor(val x: Float, val y: Float, val optionIndex: Int, val text: String)
data class Laser(val x: Float, val y: Float)

@Composable
fun GameScreen(
    questions: List<GameQuestion>,
    serverIp: String,
    onBackToChat: () -> Unit,
    onPlayAgain: () -> Unit
) {
    var currentQuestionIdx by remember { mutableStateOf(0) }
    var score by remember { mutableStateOf(0) }
    var lives by remember { mutableStateOf(3) }
    var isOver by remember { mutableStateOf(false) }
    var isWon by remember { mutableStateOf(false) }

    if (questions.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background), contentAlignment = Alignment.Center) {
            Text("No questions loaded", color = TextLight)
        }
        return
    }

    val currentQuestion = questions.getOrNull(currentQuestionIdx) ?: questions.first()

    // Screen dimensions
    var width by remember { mutableStateOf(0f) }
    var height by remember { mutableStateOf(0f) }

    // SpaceShip position
    var shipX by remember { mutableStateOf(0f) }

    // Lists of game objects
    val lasers = remember { mutableStateListOf<Laser>() }
    val meteors = remember { mutableStateListOf<Meteor>() }
    var starOffset by remember { mutableStateOf(0f) }

    // Initialize meteors when question changes
    LaunchedEffect(currentQuestionIdx, width) {
        if (width > 0) {
            shipX = width / 2f
            lasers.clear()
            meteors.clear()
            // Spawn 4 meteors horizontally spaced
            val step = width / 5f
            for (i in 0 until 4) {
                meteors.add(
                    Meteor(
                        x = step * (i + 1),
                        y = 100f + (Math.random() * 80).toFloat(), // staggered heights
                        optionIndex = i,
                        text = when(i) {
                            0 -> "A"
                            1 -> "B"
                            2 -> "C"
                            else -> "D"
                        }
                    )
                )
            }
        }
    }

    // Game loop ticks (60 FPS)
    LaunchedEffect(isOver, isWon, currentQuestionIdx, width, height) {
        while (!isOver && !isWon) {
            delay(16L) // ~60fps
            starOffset = (starOffset + 1.2f) % 2000f

            // 2. Move lasers up (thread-safe copy updates) - reduced speed to 8f
            val updatedLasers = lasers.map { it.copy(y = it.y - 8f) }.filter { it.y >= 0 }
            lasers.clear()
            lasers.addAll(updatedLasers)

            // 3. Move meteors down (thread-safe copy updates)
            val updatedMeteors = meteors.map {
                var newY = it.y + 4f
                if (newY > height && height > 0) {
                    newY = 50f
                }
                it.copy(y = newY)
            }
            meteors.clear()
            meteors.addAll(updatedMeteors)

            // 4. Collision detection
            var hitWrong = false
            var hitCorrect = false
            val lasersToRemove = mutableListOf<Laser>()
            
            for (laser in lasers) {
                for (meteor in meteors) {
                    val distance = Math.hypot((laser.x - meteor.x).toDouble(), (laser.y - meteor.y).toDouble())
                    if (distance < 50.0) { // Collision threshold
                        lasersToRemove.add(laser)
                        if (meteor.optionIndex == currentQuestion.correctIndex) {
                            hitCorrect = true
                        } else {
                            hitWrong = true
                        }
                    }
                }
            }

            if (lasersToRemove.isNotEmpty()) {
                lasers.removeAll(lasersToRemove)
            }
            
            if (hitCorrect) {
                score += 10
                if (currentQuestionIdx + 1 < questions.size) {
                    currentQuestionIdx++
                } else {
                    isWon = true
                }
            } else if (hitWrong) {
                lives--
                if (lives <= 0) {
                    isOver = true
                } else {
                    // Reset ALL meteors to top and clear lasers
                    val resetMeteors = meteors.map {
                        it.copy(y = 100f + (Math.random() * 80).toFloat())
                    }
                    meteors.clear()
                    meteors.addAll(resetMeteors)
                    lasers.clear()
                }
            }
        }
    }

    // Layout
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Top row: Back button, score, lives
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onBackToChat) {
                Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = TextLight)
            }
            Text("Score: $score", color = PrimaryIndigo, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
            Text("Lives: " + "❤️".repeat(lives), color = AccentError, fontSize = 14.sp)
        }

        Spacer(modifier = Modifier.height(8.dp))

        if (isOver || isWon) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = if (isWon) "🏆 VICTORY!" else "💥 GAME OVER",
                        color = if (isWon) SecondaryCyan else AccentError,
                        fontSize = 28.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Final Score: $score", color = TextLight, fontSize = 18.sp)
                    Spacer(modifier = Modifier.height(16.dp))
                    val playAgainInteraction = remember { MutableInteractionSource() }
                    Button(
                        onClick = onPlayAgain,
                        interactionSource = playAgainInteraction,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = PrimaryIndigo,
                            contentColor = MaterialTheme.colorScheme.onPrimary
                        ),
                        modifier = Modifier.bounceClick(playAgainInteraction)
                    ) {
                        Text("Play Again")
                    }
                }
            }
        } else {
            // Display Question
            Text(
                text = "Q${currentQuestionIdx + 1}/${questions.size}: ${currentQuestion.question}",
                color = TextLight,
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp)
            )

            // Game Canvas
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .background(DarkSurfaceField, shape = RoundedCornerShape(12.dp))
                    .pointerInput(Unit) {
                        detectDragGestures { change, dragAmount ->
                            change.consume()
                            shipX = (shipX + dragAmount.x).coerceIn(40f, width - 40f)
                        }
                    }
                    .pointerInput(Unit) {
                        detectTapGestures {
                            // Shoot laser manually
                            lasers.add(Laser(shipX, height - 120f))
                        }
                    },
                contentAlignment = Alignment.Center
            ) {
                Canvas(modifier = Modifier
                    .fillMaxSize()
                    .onGloballyPositioned {
                        width = it.size.width.toFloat()
                        height = it.size.height.toFloat()
                        if (shipX == 0f) shipX = width / 2f
                    }) {
                    // Draw Scrolling Stars Background (Parallax Effect)
                    for (i in 0 until 24) {
                        val speed = if (i % 2 == 0) 1.5f else 0.8f
                        val starY = ((height * (i * 3 % 10) / 10f) + starOffset * speed) % height
                        drawCircle(
                            color = TextMuted.copy(alpha = if (i % 2 == 0) 0.45f else 0.25f),
                            radius = if (i % 2 == 0) 2.5f else 1.5f,
                            center = androidx.compose.ui.geometry.Offset((width * (i * 7 % 10) / 10f), starY)
                        )
                    }

                    // Draw Lasers
                    lasers.forEach { laser ->
                        drawRect(
                            color = SecondaryCyan,
                            topLeft = androidx.compose.ui.geometry.Offset(laser.x - 2f, laser.y - 10f),
                            size = androidx.compose.ui.geometry.Size(4f, 20f)
                        )
                    }

                    // Native paint for centering letter A, B, C, D in meteor circles
                    val textPaint = android.graphics.Paint().apply {
                        color = android.graphics.Color.rgb(242, 237, 227)
                        textSize = 36f
                        textAlign = android.graphics.Paint.Align.CENTER
                        isFakeBoldText = true
                    }

                    // Draw Meteors (Detailed retro vector asteroids)
                    meteors.forEach { meteor ->
                        // Draw solid filled inner body
                        drawCircle(
                            color = DarkSurfaceCard,
                            radius = 32f,
                            center = androidx.compose.ui.geometry.Offset(meteor.x, meteor.y)
                        )
                        // Outer concentric rim
                        drawCircle(
                            color = AccentError,
                            radius = 32f,
                            center = androidx.compose.ui.geometry.Offset(meteor.x, meteor.y),
                            style = androidx.compose.ui.graphics.drawscope.Stroke(width = 3f)
                        )
                        // Inner ring outline
                        drawCircle(
                            color = AccentError.copy(alpha = 0.5f),
                            radius = 26f,
                            center = androidx.compose.ui.geometry.Offset(meteor.x, meteor.y),
                            style = androidx.compose.ui.graphics.drawscope.Stroke(width = 1.5f)
                        )
                        // Asteroid surface craters
                        drawCircle(
                            color = AccentError.copy(alpha = 0.4f),
                            radius = 6f,
                            center = androidx.compose.ui.geometry.Offset(meteor.x - 12f, meteor.y - 8f),
                            style = androidx.compose.ui.graphics.drawscope.Stroke(width = 1.5f)
                        )
                        drawCircle(
                            color = AccentError.copy(alpha = 0.4f),
                            radius = 4f,
                            center = androidx.compose.ui.geometry.Offset(meteor.x + 10f, meteor.y + 10f),
                            style = androidx.compose.ui.graphics.drawscope.Stroke(width = 1.5f)
                        )
                        // Draw centered option letter directly on canvas
                        drawContext.canvas.nativeCanvas.drawText(
                            meteor.text,
                            meteor.x,
                            meteor.y + 12f, // center offset for 36f size
                            textPaint
                        )
                    }

                    // Draw Player Ship (Sleek vector space craft)
                    val shipPath = androidx.compose.ui.graphics.Path().apply {
                        moveTo(shipX, height - 120f)
                        lineTo(shipX - 24f, height - 75f)
                        lineTo(shipX - 12f, height - 82f)
                        lineTo(shipX + 12f, height - 82f)
                        lineTo(shipX + 24f, height - 75f)
                        close()
                    }
                    drawPath(
                        path = shipPath,
                        color = PrimaryIndigo
                    )
                    // Flickering thruster flame
                    val flamePath = androidx.compose.ui.graphics.Path().apply {
                        moveTo(shipX - 8f, height - 74f)
                        lineTo(shipX, height - 56f - (Math.random() * 8).toFloat())
                        lineTo(shipX + 8f, height - 74f)
                        close()
                    }
                    drawPath(
                        path = flamePath,
                        color = AccentWarning
                    )
                }

                // Floating Fire Button
                Box(
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(24.dp)
                        .size(70.dp)
                        .background(AccentError, shape = CircleShape)
                        .bounceClickable {
                            if (height > 0) {
                                lasers.add(Laser(shipX, height - 120f))
                            }
                        },
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "FIRE",
                        color = Color(0xFF331613),
                        fontWeight = FontWeight.Black,
                        fontSize = 16.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Display MCQ Options details at the bottom of the screen
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(DarkSurfaceCard, shape = RoundedCornerShape(8.dp))
                    .padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                currentQuestion.options.forEachIndexed { idx, option ->
                    val letter = when(idx) {
                        0 -> "A"
                        1 -> "B"
                        2 -> "C"
                        else -> "D"
                    }
                    Text(
                        text = "$letter: $option",
                        color = TextLight,
                        fontSize = 12.sp
                    )
                }
            }
        }
    }
}
