package dev.transcribelab.android

data class Segment(val startSeconds: Float, val endSeconds: Float, val text: String)

class WhisperBridge {
    fun interface ProgressListener {
        fun onProgress(percent: Int)
    }

    external fun process(
        modelPath: String,
        samples: FloatArray,
        sourceLanguage: String,
        translateToEnglish: Boolean,
        prompt: String,
        progressListener: ProgressListener,
    ): ArrayList<Segment>

    external fun cancel()

    companion object {
        init {
            System.loadLibrary("transcribe_native")
        }
    }
}
