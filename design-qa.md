# Transcribe Lab design QA

## Build under review

- Product: Transcribe Lab 2.0.0
- Platform: macOS 14+ on Apple silicon
- Reference: selected Option 3 Transcribe Lab concept
- Release commit: `feat: build Transcribe Lab interface`

## Required viewport matrix

| Width | Layout expectation | Result |
| --- | --- | --- |
| 320 | One-column mobile, no horizontal clipping | Pass |
| 375 | One-column mobile, touch-safe controls | Pass |
| 390 | One-column mobile, readable metadata | Pass |
| 640 | One-column compact layout | Pass |
| 768 | Two-column tablet workspace | Pass |
| 1024 | Two-column tablet workspace | Pass |
| 1025 | Two-column breakpoint boundary | Pass |
| 1279 | Three-column desktop workspace | Pass |
| 1280 | Three-column desktop workspace | Pass |
| 1440 | Three-column desktop workspace | Pass |

## Functional evidence

- Automated suite: 25 tests passed.
- Python source and tests compile successfully.
- FFprobe read the real AIFF as 8.65 seconds, 376 KB, 22.05 kHz, mono.
- FFmpeg produced a 900-point waveform from the real audio stream.
- A 1–5 second Turkish selection completed as an English SRT in 5–6 seconds.
- The GUI command preview matched the executed CLI range and translation flags.
- Media delivery returned a valid 206 byte range; missing token returned 403.
- Dark and light themes were rendered and inspected at desktop width.
- Light primary-action contrast was corrected to 5.17:1.
- Keyboard focus reached the interactive controls with accessible names.
- All matrix widths reported document width equal to viewport width.
- No browser console errors or page errors were recorded at any matrix width.
- Reference screenshots inspected: 320, 768, 1440 dark, 1440 light, and
  1440 successful selected-range processing.

## Open defects

No release-blocking defects found. Browser-native playback remains codec
dependent by design; waveform generation and transcription continue through
FFmpeg when the browser cannot preview a format.
