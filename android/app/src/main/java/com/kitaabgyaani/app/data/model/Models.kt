package com.kitaabgyaani.app.data.model

data class StudyResponse(
    val summary: String = "",
    val flashcards: List<Flashcard> = emptyList(),
    val mcqs: List<MCQ> = emptyList()
)

data class Flashcard(
    val q: String,
    val a: String
)

data class MCQ(
    val q: String,
    val options: List<String>,
    val answer: String
)

data class PlannerResponse(
    val exam_name: String = "",
    val exam_date: String = "",
    val schedule: List<ScheduleItem> = emptyList(),
    val milestones: List<Milestone> = emptyList()
)

data class ScheduleItem(
    val day: Int,
    val date: String,
    val topics: List<String>,
    val duration_hours: Int,
    val study_load: String,
    val resources: List<String>
)

data class Milestone(
    val day: Int,
    val milestone: String
)

data class ExpenseResponse(
    val amount: Double = 0.0,
    val category: String = "",
    val merchant: String = "",
    val date: String = "",
    val confidence: Double = 0.0
)

data class ContentResponse(
    val draft_text: String = "",
    val suggestions: List<String> = emptyList(),
    val tone: String = ""
)

data class WebSocketRequest(
    val id: String,
    val agent: String,
    val action: String,
    val payload: Map<String, Any>
)

data class WebSocketResponse(
    val request_id: String,
    val status: String,
    val agent: String,
    val data: Any?,
    val processing_time_ms: Long,
    val server_timestamp: Long
)
