# Transcribe Lab design direction

## Locked concept

Transcribe Lab uses the selected Option 3 direction: a dense, code-focused
local media workbench rather than a generic upload form.

The defining elements are:

- a scalable multi-file session library;
- real technical media metadata;
- a decoded waveform with seeking and selectable transcription ranges;
- persistent, enforced local/private status;
- transcription settings beside an exact CLI command preview;
- live process output with progress, elapsed time, remaining time and speed;
- dark amber/lime styling with a user-controlled light theme.

## Interaction principles

The selected file remains the center of the workspace. Advanced detail is
visible but grouped, and every GUI choice maps to a command the user can learn
and reuse. The interface must remain useful without browser playback because
FFmpeg supports more codecs than browsers do.

Desktop uses a three-column workbench. Tablet moves settings beneath the media
viewer. Mobile becomes a single readable stack with touch-safe controls and a
shorter waveform. Reduced-motion preferences disable nonessential transitions.
