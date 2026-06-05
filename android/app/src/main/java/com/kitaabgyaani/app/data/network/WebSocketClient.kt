package com.kitaabgyaani.app.data.network

import com.google.gson.Gson
import com.kitaabgyaani.app.data.model.WebSocketRequest
import okhttp3.*
import java.util.concurrent.TimeUnit

class WebSocketClient(private val listener: WebSocketListenerInterface) {

    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private val gson = Gson()

    interface WebSocketListenerInterface {
        fun onConnected()
        fun onDisconnected()
        fun onMessageReceived(text: String)
        fun onError(error: String)
    }

    fun connect(url: String) {
        val request = Request.Builder().url(url).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                listener.onConnected()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                listener.onMessageReceived(text)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
                listener.onDisconnected()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                listener.onError(t.message ?: "Unknown socket error")
            }
        })
    }

    fun send(request: WebSocketRequest) {
        val json = gson.toJson(request)
        webSocket?.send(json)
    }

    fun disconnect() {
        webSocket?.close(1000, "Normal closure")
        webSocket = null
    }
}
