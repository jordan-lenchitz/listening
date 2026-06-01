%% quick_start.m - Quick Start for Multi-F0 Tracker
%
% minimal reference examples showing how to use the tracker :)

%% Example 1: Basic usage
[audio, sr] = audioread("your_audio.wav");

tracker = MultiF0Tracker();
result = tracker.track(audio, sr);

result.visualize();
result.summary();

%% Example 2: Barbershop quartet settings
tracker = MultiF0Tracker( ...
    MaxVoices=4, ...
    MinFreq=80, ...
    MaxFreq=500, ...
    PeakThreshold=0.15, ...
    DetectExtraPitches=true);

result = tracker.track(audio, sr);

% Export for analysis
result.exportCSV("pitches.csv");

%% Example 3: Access individual voices
voice1 = result.getVoice(1);  % Returns timetable
plot(voice1.Time, voice1.Frequency_Hz);

%% Example 4: Custom visualization
result.visualize( ...
    Title="My Recording", ...
    ShowGhosts=false, ...
    YLim=[80, 400], ...
    OutputPath="my_plot.png");

%% Configuration Reference
%
% Audio:
%   SampleRate (22050)    - Target sample rate
%   HopLength (512)       - STFT hop in samples
%   FrameLength (4096)    - STFT frame in samples
%
% Pitch Detection:
%   MinFreq (65)          - Min F0 in Hz (~C2)
%   MaxFreq (1400)        - Max F0 in Hz
%   MaxVoices (8)         - Max simultaneous voices
%   PeakThreshold (0.1)   - Salience threshold (0-1)
%
% Tracking:
%   MaxPitchJumpCents (300)  - Max pitch jump (~3 semitones)
%   TentativeFrames (3)      - Frames to confirm new voice
%   InactiveFrames (5)       - Frames to terminate voice
%
% Ghost Detection:
%   DetectExtraPitches (true)       - Enable combination tone detection
%   CombinationToneTolerance (30)   - Tolerance in cents
%   OvertoneTolerance (20)          - Overtone tolerance in cents

