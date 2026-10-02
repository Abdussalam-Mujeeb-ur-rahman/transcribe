# Transcribe Lab for Android — beta

This is an early native Android prototype, separate from the Apple Silicon
Mac app. Its intended path is **WhatsApp → Share → Transcribe Lab → text**,
without a terminal, account, or audio upload. The app also has a file picker.
It can transcribe speech in its original language (English to English, Spanish
to Spanish, and other supported languages) or translate speech into English.
Processing runs on the phone with `whisper.cpp`.

![Transcribe Lab on Android showing a Spanish-to-English result with timed segments and Copy, Share, and Save actions](../docs/images/transcribe-android-result-first.png)

*Pixel 7 prototype with a synthetic 49-second Spanish voice note. This shows the
result screen, not a guarantee of word-for-word accuracy on every recording.*

## Download and install

The signed [Android beta APK](https://github.com/Abdussalam-Mujeeb-ur-rahman/transcribe/releases/download/v0.2.0-beta.2/transcribe-lab-android-v0.2.0-beta.2.apk)
is available from the [v0.2.0-beta.2 release](https://github.com/Abdussalam-Mujeeb-ur-rahman/transcribe/releases/tag/v0.2.0-beta.2).
It is for Android 10+ ARM64 phones. The Mac installer and GitHub source-code
ZIP are not Android installers.

1. On your phone, download the **APK** from the release page and open it.
   If Android asks, allow installation from the browser or Files app you used.
2. Open Transcribe Lab and choose a multilingual model:
   - **Base (~142 MiB):** faster processing and a smaller download.
   - **Small (~466 MiB):** slower processing and a larger download, but may
     produce a more accurate transcript or translation, especially on difficult
     speech. Despite its name, Small is larger than Base.
   Download the model once with internet; processing then runs locally. Small
   is an accuracy-oriented choice, not a guarantee that every word is correct.
3. Choose an audio recording, select **Transcribe** to keep its spoken language
   or **Translate to English**, then review, copy, share, or save the result.
   For translation, the app first transcribes the original speech, then locally
   translates the written transcript. The original remains available to expand
   beneath the English result.

On Android 12+, tap **Manage offline languages** to open Settings and search
for **Live Translate** or **offline languages**. Install the source language
pack (for example, Spanish) if translation asks for it. The system
may default to Wi-Fi-only downloads; you can change that in its language
settings if you choose to use mobile data. If the system translator is not
available, the app tries a separate on-device ML Kit language pack. First-time
pack downloads need internet and can take time. Audio and text processing stay
on the phone. If a pack is unavailable or translation fails, the original
transcript is retained; **Retry English Translation** does not run speech
recognition again. Review names and important details before sharing.

This is a pre-release, not a stable Android launch. Direct sharing from
WhatsApp into this build, real-world Small-model accuracy, long
recordings, and subtitle save/share on-device still need broader testing. Keep
the app open during processing and review important words before using the
transcript.

**Already using the Pixel debug APK?** It has a different signing certificate.
Save any transcript you need, uninstall that debug app, then install this beta.
Uninstalling removes app-private models and unsaved data; the model will need
downloading again. Later signed beta updates can install over this release.

APK SHA-256: `5d1769a8b65f633a20873e281c6d7ca1cf3998c8ba402accbe9d6b64ca9ffbe4`.
The matching [checksum file](https://github.com/Abdussalam-Mujeeb-ur-rahman/transcribe/releases/download/v0.2.0-beta.2/transcribe-lab-android-v0.2.0-beta.2.apk.sha256)
is attached to the release.

## Current scope

- Android 10+ on ARM64, with a Pixel 7 as the first intended test device.
- Shared audio and the system picker; automatic detection or an explicit spoken
  language, including English, Spanish, Turkish, Chinese, Korean, Portuguese,
  French, German, Arabic, and Hindi.
- Transcription in the spoken language or translation into English. The selected
  task is visible before processing, rather than silently translating English.
- TXT, SRT, VTT, TSV, or JSON output with copy, Android text share, and save.
  Timed segments can be edited before export.
- A result-first phone layout: completed transcript segments appear immediately
  below the recording and language direction, with Copy, Share, Save, and
  **Transcribe New Voice Note** kept at the bottom. Settings expand only when
  needed, and the selected recording has an on-device playback control.
- The multilingual Base model (about 142 MiB) or optional multilingual Small
  model (about 466 MiB). Each is downloaded once and integrity-checked. Small
  may improve difficult wording, but requires more space and runs slower; it
  does not guarantee the correct words.
- Animated processing feedback while the native engine has not yet reported a
  percentage; elapsed time and true percentage when one becomes available.
- Up to 10 minutes or 100 MB per recording in this prototype.
- Keep the app open during processing. Background processing, notification
  controls, and multi-file jobs are not built yet.

On a Pixel 7 running Android 17, a 49-second synthetic Spanish Opus sample
passed the complete Small-model path: Spanish source transcript, local English
text translation, and TXT export of the English result. The original Spanish
remained expandable on screen. The installed system translation pack passed a
separate Spanish-to-English test with Wi-Fi and mobile data both disabled.
Earlier beta checks covered English transcription, Spanish transcription,
timed SRT, an Android-granted `ACTION_SEND` URI, and nonzero progress feedback.
These checks do **not** prove word-for-word accuracy on a client's voice note,
direct WhatsApp sharing, reliable first-time language-pack downloads on every
network, or sustained performance and battery use on long recordings.

Speech recognition can mishear a phrase that is acoustically ambiguous. The
app does not silently rewrite guessed words into a different meaning. For
better results, choose the spoken language explicitly, try Small if available,
add names or unusual terms as optional hints, then review/edit important words
before sharing or saving. Subtitle timestamps remain attached to each edited
segment.

## Build

The published `v0.2.0-beta.2` APK includes the two-stage local English
translation flow. On Android 12+, an installed system translation pack is
preferred; if unavailable, Google ML Kit attempts an on-device model download.
Whisper transcribes the original speech first. Downloading models may contact
their provider, but the voice note and transcript are not sent to a hosted
transcription or translation API. Automatic translations still need review,
especially for names and business details.

Install JDK 17 and the Android SDK with platform 36, build tools 36.0.0,
NDK 28.2.13676358, and CMake 3.22.1. Set `ANDROID_HOME` to your SDK path.
From this directory run:

```bash
./gradlew :app:assembleDebug
```

The build downloads the pinned `whisper.cpp` source. The debug APK is written
to `app/build/outputs/apk/debug/app-debug.apk`. Install on a connected Pixel
with `adb install -r app/build/outputs/apk/debug/app-debug.apk`.

The first launch needs internet to download the model. The app does not request
broad file access; shared recordings are copied into app-private temporary
storage for decoding and then removed. The model remains in private app storage.

## Future beta updates

Maintainers should increase `versionCode` for each new APK, build a release APK,
and sign it with the **same release key** used for this beta. Publish the new
APK on GitHub Releases. With the same app ID and signing key, Android can
install a newer version over an existing release without downloading the model
again. The release key and its password are stored outside this repository;
keep a secure backup of both and never commit them. The earlier Pixel debug
build uses a different key and cannot be updated in place to the first beta.

## First physical-device check

1. Open the app, download Base, and confirm that it says the model is ready.
2. In WhatsApp, share a short Spanish voice note to Transcribe Lab.
3. Confirm the correct voice note name appears. Choose **Transcribe** and
   **Spanish**, and confirm the result stays in Spanish. Then choose
   **Translate to English** and confirm the English result.
4. Repeat with an English voice note in **Transcribe** mode. Review the wording,
   edit a segment, and check TXT and SRT saving. Watch the animated processing
   feedback, cancellation, and whether the app stays responsive.
5. Only if you want the extra download, try Small on a difficult recording and
   compare results. Also observe run time, heat, and battery on longer notes.

Until a real WhatsApp-share check passes, this should be treated as a public
beta rather than a supported stable Android release.
