# Губка Спанч - precise mode (read only when the person has the source clips)

## Precise mode - the reel plus the source clips it was cut from
Use this only when the person has the original clips and wants an exact copy of a hand edit.

The result is `styles/<name>.json`, plus fitted `.cube` LUTs and any overlays or stickers in `library/`. Verify it by rebuilding the reference and running `python -m autocut.compare ref.mov out.mp4`; the target is a mean difference under 8/255. Measure every value; never eyeball. Work on the user's Mac in the GRIN Reels folder, using small decodes so RAM stays low.

## Steps
1. **Probe** every file with `ffprobe` (size, fps, rotation, audio). A `te_is_reencode` tag means the reference was exported from CapCut.
2. **Contact sheet:** take at most 8 key frames, 200 px wide, and look at them **once** to get the structure, the text and the stickers.
3. **A-roll segments:** decode mono 8 kHz audio. For each 0.5 s window of the reference, run a normalised FFT cross-correlation against the A-roll; a score above 0.9 is voice. Refine each offset within ±30 ms, then place cuts with a 0.25 s RMS-envelope correlation. Cuts usually hide under B-roll.
4. **B-roll mapping:** decode at 54x96 gray and 30 fps. Find each reference frame's best match by max normalised correlation, then fit a line per run to get `in` and `speed`; fit speed at the clip's native fps.
5. **Framing:** run SIFT and `estimateAffinePartial2D` on a reference/source frame pair with the caption band masked. Then `x = (tx + (s-1)W/2)/(W/2)` and `y = -(ty + (s-1)H/2)/(H/2)`.
6. **Grade:**
   - Render a version without LUTs and compare it to the reference frame-exact at 270x480.
   - A vertical darkening gradient means a shadow layer; model it as a black PNG gradient in `library/overlays/`.
   - Fit per-channel median curves on the **top half only**, separately for A-roll, colour B-roll and B&W luma, and write them as 33³ `.cube` files.
   - Store `input_luma`, measured with `media.median_luma` on the same source span.
7. **Text:**
   - Threshold white and accent pixels in the caption band to get on/off times, bounding boxes and line pitch.
   - Calibrate libass font sizes by rendering and measuring; libass comes out about 1.6–1.7× the PIL size.
   - Condensed titles may need `scale_y`.
   - Create static instances of variable fonts (`fontTools.varLib.instancer`), because libass renders a variable font as Thin.
   - Use only fonts with a commercial licence (OFL or bought).
8. **Audio bed:** subtract the aligned voice (search ±200 samples, least-squares gain) and look at the residual spectrogram. Get BPM from low-band onset autocorrelation and check whether the B-roll cuts fall every 2 beats.
9. **Sticker and end:** track the sticker's bounding box per frame for pop timing and scale, and read the fade from mean brightness.
10. **Rebuild:** write an exact rebuild spec, render it, compare, and fix the worst seconds first.
11. **Generalise:** strip the timings and keep the looks and rules (caption rules, title template, B-roll window and beats, slow-mo, CTA, fade, music gain and BPM). Add a planner regression test from a fake transcript, with the good takes where the editor cut and failed takes earlier.

## Pitfalls
- Contact sheets made with `fps=3` can show the wrong frame, so trust frame-indexed comparisons.
- Audio resampling breaks sample-wise subtraction; use envelopes to detect cuts.
- Don't normalise B-roll exposure by default, because it flattens intentional mood.
- Never ship a client's footage, voice, face or texts inside a style without their written consent.
