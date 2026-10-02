#include <jni.h>

#include <algorithm>
#include <atomic>
#include <string>
#include <vector>

#include "whisper.h"

namespace {
std::atomic<bool> cancelled{false};
std::atomic<bool> running{false};

struct RunGuard {
    ~RunGuard() {
        cancelled.store(false);
        running.store(false);
    }
};

struct ProgressContext {
    JavaVM *vm;
    jobject listener;
    jmethodID method;
};

void throwError(JNIEnv *env, const char *message) {
    jclass exceptionClass = env->FindClass("java/lang/IllegalStateException");
    if (exceptionClass != nullptr) {
        env->ThrowNew(exceptionClass, message);
    }
}

jstring utf8String(JNIEnv *env, const char *value) {
    const auto length = static_cast<jsize>(std::char_traits<char>::length(value));
    jbyteArray bytes = env->NewByteArray(length);
    if (bytes == nullptr) return nullptr;
    env->SetByteArrayRegion(bytes, 0, length, reinterpret_cast<const jbyte *>(value));

    jclass stringClass = env->FindClass("java/lang/String");
    jmethodID constructor = env->GetMethodID(stringClass, "<init>", "([BLjava/lang/String;)V");
    jstring encoding = env->NewStringUTF("UTF-8");
    auto result = static_cast<jstring>(env->NewObject(stringClass, constructor, bytes, encoding));
    env->DeleteLocalRef(encoding);
    env->DeleteLocalRef(bytes);
    env->DeleteLocalRef(stringClass);
    return result;
}

void onProgress(whisper_context *, whisper_state *, int progress, void *userData) {
    auto *context = static_cast<ProgressContext *>(userData);
    JNIEnv *env = nullptr;
    bool attached = false;
    if (context->vm->GetEnv(reinterpret_cast<void **>(&env), JNI_VERSION_1_6) != JNI_OK) {
        if (context->vm->AttachCurrentThread(&env, nullptr) != JNI_OK) return;
        attached = true;
    }
    env->CallVoidMethod(context->listener, context->method, std::clamp(progress, 0, 100));
    if (env->ExceptionCheck()) env->ExceptionClear();
    if (attached) context->vm->DetachCurrentThread();
}

bool shouldAbort(void *) {
    return cancelled.load();
}
}  // namespace

extern "C" JNIEXPORT void JNICALL
Java_dev_transcribelab_android_WhisperBridge_cancel(JNIEnv *, jobject) {
    cancelled.store(true);
}

extern "C" JNIEXPORT jobject JNICALL
Java_dev_transcribelab_android_WhisperBridge_process(
    JNIEnv *env,
    jobject,
    jstring modelPath,
    jfloatArray samples,
    jstring sourceLanguage,
    jstring prompt,
    jobject progressListener
) {
    bool expected = false;
    if (!running.compare_exchange_strong(expected, true)) {
        throwError(env, "A recording is already being processed.");
        return nullptr;
    }
    RunGuard guard;
    cancelled.store(false);

    if (modelPath == nullptr || samples == nullptr || sourceLanguage == nullptr ||
        prompt == nullptr || progressListener == nullptr) {
        throwError(env, "A model, recording, language, and progress listener are required.");
        return nullptr;
    }

    const char *modelChars = env->GetStringUTFChars(modelPath, nullptr);
    const char *languageChars = env->GetStringUTFChars(sourceLanguage, nullptr);
    const char *promptChars = env->GetStringUTFChars(prompt, nullptr);
    if (modelChars == nullptr || languageChars == nullptr || promptChars == nullptr) {
        if (modelChars != nullptr) env->ReleaseStringUTFChars(modelPath, modelChars);
        if (languageChars != nullptr) env->ReleaseStringUTFChars(sourceLanguage, languageChars);
        if (promptChars != nullptr) env->ReleaseStringUTFChars(prompt, promptChars);
        return nullptr;
    }
    const std::string model(modelChars);
    const std::string language(languageChars);
    const std::string speechHint(promptChars);
    env->ReleaseStringUTFChars(modelPath, modelChars);
    env->ReleaseStringUTFChars(sourceLanguage, languageChars);
    env->ReleaseStringUTFChars(prompt, promptChars);

    const jsize count = env->GetArrayLength(samples);
    if (count <= 0) {
        throwError(env, "The recording contains no audio samples.");
        return nullptr;
    }
    std::vector<float> audio(static_cast<size_t>(count));
    env->GetFloatArrayRegion(samples, 0, count, audio.data());
    if (env->ExceptionCheck()) return nullptr;

    whisper_context_params contextParams = whisper_context_default_params();
    contextParams.use_gpu = false;
    whisper_context *context = whisper_init_from_file_with_params(model.c_str(), contextParams);
    if (context == nullptr) {
        throwError(env, "The speech model could not be opened.");
        return nullptr;
    }

    JavaVM *vm = nullptr;
    env->GetJavaVM(&vm);
    jclass listenerClass = env->GetObjectClass(progressListener);
    const jmethodID progressMethod = env->GetMethodID(listenerClass, "onProgress", "(I)V");
    env->DeleteLocalRef(listenerClass);
    if (progressMethod == nullptr) {
        whisper_free(context);
        return nullptr;
    }
    jobject globalListener = env->NewGlobalRef(progressListener);
    if (globalListener == nullptr) {
        whisper_free(context);
        return nullptr;
    }
    ProgressContext progressContext{vm, globalListener, progressMethod};

    whisper_full_params params = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
    params.n_threads = 4;
    params.language = language.c_str();
    params.translate = false;
    params.initial_prompt = speechHint.empty() ? nullptr : speechHint.c_str();
    params.no_timestamps = false;
    params.print_progress = false;
    params.print_realtime = false;
    params.print_timestamps = false;
    params.progress_callback = onProgress;
    params.progress_callback_user_data = &progressContext;
    params.abort_callback = shouldAbort;

    const int status = cancelled.load() ? -1 : whisper_full(context, params, audio.data(), count);
    env->DeleteGlobalRef(globalListener);
    if (status != 0 || cancelled.load()) {
        whisper_free(context);
        throwError(env, cancelled.load() ? "Processing cancelled." : "The recording could not be processed.");
        return nullptr;
    }

    jclass listClass = env->FindClass("java/util/ArrayList");
    jmethodID listConstructor = env->GetMethodID(listClass, "<init>", "()V");
    jmethodID addMethod = env->GetMethodID(listClass, "add", "(Ljava/lang/Object;)Z");
    jobject results = env->NewObject(listClass, listConstructor);
    jclass segmentClass = env->FindClass("dev/transcribelab/android/Segment");
    jmethodID segmentConstructor = env->GetMethodID(segmentClass, "<init>", "(FFLjava/lang/String;)V");

    if (!env->ExceptionCheck() && results != nullptr && segmentConstructor != nullptr) {
        const int segments = whisper_full_n_segments(context);
        for (int index = 0; index < segments; ++index) {
            const auto start = static_cast<jfloat>(whisper_full_get_segment_t0(context, index) / 100.0);
            const auto end = static_cast<jfloat>(whisper_full_get_segment_t1(context, index) / 100.0);
            jstring text = utf8String(env, whisper_full_get_segment_text(context, index));
            jobject segment = env->NewObject(segmentClass, segmentConstructor, start, end, text);
            env->CallBooleanMethod(results, addMethod, segment);
            env->DeleteLocalRef(segment);
            env->DeleteLocalRef(text);
            if (env->ExceptionCheck()) break;
        }
    }

    const int detectedLanguageId = whisper_full_lang_id(context);
    const char *detectedLanguage = detectedLanguageId >= 0 ? whisper_lang_str(detectedLanguageId) : language.c_str();
    jstring languageResult = env->NewStringUTF(detectedLanguage);
    jclass resultClass = env->FindClass("dev/transcribelab/android/WhisperResult");
    jmethodID resultConstructor = resultClass == nullptr ? nullptr :
        env->GetMethodID(resultClass, "<init>", "(Ljava/util/ArrayList;Ljava/lang/String;)V");
    jobject result = resultConstructor == nullptr ? nullptr :
        env->NewObject(resultClass, resultConstructor, results, languageResult);
    if (resultClass != nullptr) env->DeleteLocalRef(resultClass);
    if (languageResult != nullptr) env->DeleteLocalRef(languageResult);
    env->DeleteLocalRef(segmentClass);
    env->DeleteLocalRef(listClass);
    whisper_free(context);
    return env->ExceptionCheck() ? nullptr : result;
}
