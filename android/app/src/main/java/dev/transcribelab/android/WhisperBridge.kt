package dev.transcribelab.android

data class Segment(val startSeconds: Float, val endSeconds: Float, val text: String)
data class WhisperResult(val segments: ArrayList<Segment>, val language: String)

class WhisperBridge {
    fun interface ProgressListener {
        fun onProgress(percent: Int)
    }

    external fun process(
        modelPath: String,
        samples: FloatArray,
        sourceLanguage: String,
        prompt: String,
        progressListener: ProgressListener,
    ): WhisperResult

    external fun cancel()

    companion object {
        init {
            System.loadLibrary("transcribe_native")
        }
    }
}
