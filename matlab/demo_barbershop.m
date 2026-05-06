%% demo_barbershop.m - Demo of Multi-F0 Tracker with Synthetic Barbershop Quartet
%
% Generates a synthetic barbershop quartet (A dominant 7th in just intonation)
% with staggered voice entries/exits
% and then runs the Multi-F0 tracker
%
% Chord voicing:
%   Bass:     A2  = 110.0 Hz  (1:1 root)
%   Baritone: C#3 = 137.5 Hz  (5:4 major third)
%   Lead:     E3  = 165.0 Hz  (3:2 perfect fifth)
%   Tenor:    G3  = 192.5 Hz  (7:4 harmonic seventh)

clear; close all; clc;

%% Configuration
sr = 22050;
duration = 9.5;  % seconds

% Voice parameters: [frequency, entry_time, exit_time]
voices = dictionary( ...
    "Bass",     [110.0,  0.5, 9.0], ...
    "Baritone", [137.5,  1.5, 8.0], ...
    "Lead",     [165.0,  2.5, 7.0], ...
    "Tenor",    [192.5,  3.5, 6.0]);

%% Generate synthetic audio
fprintf("🎵 Generating synthetic barbershop quartet...\n\n");

t = (0:round(duration*sr)-1)' / sr;
audio = zeros(size(t));

voiceNames = keys(voices);
for i = 1:numel(voiceNames)
    name = voiceNames(i);
    params = voices(name);
    f0 = params(1); entry = params(2); exit = params(3);
    
    audio = audio + synthesizeVoice(t, f0, entry, exit, sr);
    fprintf("  %s: %.1f Hz (%.1fs → %.1fs)\n", name, f0, entry, exit);
end

audio = audio / max(abs(audio)) * 0.9;

% Save audio
audiowrite("demo_barbershop.wav", audio, sr);
fprintf("\n✓ Audio saved: demo_barbershop.wav\n");

%% Run tracker
fprintf("\n🔍 Running Multi-F0 Tracker...\n\n");

tracker = MultiF0Tracker( ...
    MaxVoices=4, ...
    MinFreq=80, ...
    MaxFreq=600, ...
    PeakThreshold=0.15, ...
    DetectExtraPitches=false);

result = tracker.track(audio, sr);

%% Filter short tracks (keep only substantive voices)
minFrames = 20;
result.SungVoices = result.SungVoices(cellfun(@(t) numel(t.Pitches) >= minFrames, result.SungVoices));

%% Visualize
fprintf("\n📊 Creating visualization...\n");

result.visualize( ...
    Title="Barbershop Quartet: A Dominant 7th (Just Intonation)", ...
    OutputPath="tracking_result.png");

%% Summary & export
result.summary();
result.exportCSV("tracking_data.csv");

fprintf("\n✅ Done!\n");

%% ===================== Helper Function =====================

function signal = synthesizeVoice(t, f0, entryTime, exitTime, sr)
    % Generate synthetic voice with vibrato and harmonics
    arguments
        t (:,1) double
        f0 (1,1) double
        entryTime (1,1) double
        exitTime (1,1) double
        sr (1,1) double
    end

    % Vibrato
    vibratoRate = 5;      % Hz
    vibratoDepth = 0.015; % 1.5%
    vibrato = vibratoDepth * sin(2*pi*vibratoRate*t);

    % Additive synthesis with formant-like weighting
    weights = [1.0, 0.7, 0.4, 0.3, 0.2, 0.15];
    signal = zeros(size(t));
    for h = 1:numel(weights)
        signal = signal + weights(h) * sin(2*pi*h*f0*t + h*vibrato);
    end

    % Amplitude envelope with smooth attack/release
    envelope = zeros(size(t));
    fadeLen = round(0.05 * sr);
    entryIdx = round(entryTime * sr) + 1;
    exitIdx = round(exitTime * sr);

    for i = 1:numel(t)
        if i < entryIdx
            envelope(i) = 0;
        elseif i < entryIdx + fadeLen
            envelope(i) = (i - entryIdx) / fadeLen;
        elseif i < exitIdx - fadeLen
            envelope(i) = 1;
        elseif i < exitIdx
            envelope(i) = (exitIdx - i) / fadeLen;
        end
    end

    envelope = smoothdata(envelope, "gaussian", 50);
    signal = signal .* envelope;
end
