# Experiments

Spikes, not library code. Nothing here is covered by tests or by the public API.

## Light organ

Listen to the room through the microphone and turn what is playing into light:
frequency bands become colors, onsets become beats, and the result is streamed
to an entertainment area over UDP.

```bash
uv pip install sounddevice numpy       # on top of hueify[entertainment]

python experiments/record.py --baseline    # does the mic hear music at all?
python experiments/compare_inputs.py      # which microphone hears the music
python experiments/mic_capture.py         # analysis only, no bridge involved
python experiments/light_organ_stream.py --area "Musikbereich" --mode pulse

python experiments/simulate.py            # no microphone, no bridge, no music
```

Use `python`, not `uv run`. These two dependencies are deliberately not in
`pyproject.toml` - this is a spike, not a feature - and `uv run` syncs against
the lockfile, which throws them straight back out.

Start with `mic_capture.py`. It draws the five bands, the detected beats and the
tempo in the terminal, which is the fastest way to tell a bad microphone signal
from a bad mapping. Only when the bars move with the music is it worth sending
anything to the lights.

### How it fits together

| Module | Responsibility |
| --- | --- |
| [audio.py](light_organ/audio.py) | Input devices, and mono blocks off PortAudio's thread |
| [analysis.py](light_organ/analysis.py) | FFT, frequency bands, onset detection, tempo |
| [visuals.py](light_organ/visuals.py) | Features to colors, one class per light show |
| [smoothing.py](light_organ/smoothing.py) | Envelopes and peak followers, so nothing flickers |
| [console.py](light_organ/console.py) | Terminal bars that survive a cp1252 console |

The runners are [mic_capture.py](mic_capture.py),
[light_organ_stream.py](light_organ_stream.py) and
[compare_inputs.py](compare_inputs.py), and [simulate.py](simulate.py)
is the tuning bench: it plays a synthetic track of known tempo through the whole
chain against real area geometries, so a parameter change can be judged in a
second rather than by playing music at the wall.

The analysis runs on the audio thread and publishes an immutable
`AudioFeatures` snapshot; the visuals read the latest one at 50 fps from the
event loop. Nothing blocks and nothing locks - if the light stream is faster
than the analysis it simply paints the same snapshot twice.

Beats are a counter, not a flag. The analyzer produces roughly 90 snapshots per
second and the stream reads 50, so a boolean would silently drop beats.

### Modes

| Mode | What it does |
| --- | --- |
| `pulse` | The room breathes with the bass, hue jumps on every beat (default) |
| `spectrum` | The room becomes an equalizer, bass on the left, treble on the right |
| `sweep` | Every beat sends a wave of color travelling across the room |

### Tuning

| Flag | Meaning |
| --- | --- |
| `--sensitivity` | Beat threshold in standard deviations. Lower finds more onsets: on a synthetic 120 BPM track 1.2 catches 42 of 48, 1.5 catches 34, 2.0 keeps only the kicks |
| `--gamma` | Brightness curve. Above 1 the quiet parts go dark and beats stand out more, at the cost of overall brightness |
| `--device` | Input device index or part of its name |
| `--max-freq` | Squeeze all five bands below this, for a microphone that cannot hear higher |
| `--rate` | Stream frames per second, up to 60 |

### The microphone is the hard part

Run [compare_inputs.py](compare_inputs.py) with music playing before anything
else. It records through every input in turn and prints the shape of what each
one heard, which is the difference between a mapping problem and a signal
problem.

A speakerphone is the worst possible choice and the most tempting one, because
it is usually the loudest device in the list. Echo cancellation exists to remove
whatever comes out of the speakers - that is the music - and noise suppression
treats the rest as something to clean up. What survives is band limited to
speech, so the top two bands sit at zero and the lamps driven by them never
light up.

If that is the only input available, `--max-freq 1600` squeezes all five bands
into the range it can actually deliver. The bands stop meaning "bass" and
"treble" and start meaning "low and high for this microphone", but every lamp
moves again.

A reading of 0.0000 is not a quiet microphone, it is a muted one - check its
level in the Windows sound settings before blaming the hardware.

When a device looks dead, [record.py](record.py) says why. It writes a WAV you
can actually listen to and reports absolute dBFS rather than the normalized
levels the light show uses, because normalizing is exactly what hides a dying
signal. `--baseline` records silence, then music, and compares the two.

The number that usually settles it is the share of samples that are **exactly
zero**. Analogue hardware always carries noise and cannot produce an exact zero,
so anything above a few percent means something is replacing the signal rather
than attenuating it. An Intel Smart Sound array measured here sat at 47% through
MME and 66% through WASAPI: a noise gate deciding that music is not speech and
cutting it away. Turning off audio enhancements for the device is the fix -
`control mmsys.cpl,,1` opens the recording tab directly.

WDM-KS entries bypass the Windows processing chain and would sidestep such a
gate, but on this machine none of them could be opened at any block size: the
array is held exclusively by the audio service.

Select devices **by name**, not by index. Windows renumbers everything whenever
a device appears or disappears - plugging in headphones shifted every index here
by several places mid-session.

### What was measured

- **Latency** is roughly 30-60 ms end to end: one 512 sample block, a 2048
  sample analysis window and one 20 ms stream frame. Well under the point where
  it stops feeling synchronous.
- **Levels are normalized against the recent peak**, not against an absolute
  scale, so the show does not depend on how loud the speakers are. The cost is
  that a long quiet passage slowly brightens back up.
- **Positions are not symmetric.** Real areas here span 0.3 to 1.0 and 0.82 to
  1.0, with two channels sharing a position, so `sweep` derives its travel from
  the lamps that actually exist rather than from the full -1..1 axis.
- **Not tried: speaker loopback.** Capturing what the PC plays instead of what
  the room hears would remove the noise and the reverb, but this `sounddevice`
  build has no WASAPI loopback flag. A "Stereomix" device, if the sound card
  offers one, works today via `--device`.
