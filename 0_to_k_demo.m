%% DYNAMIC 0-K MULTI-F0 TRACKING - MAIN DEMONSTRATION SCRIPT
% =========================================================================
% a reference MATLAB implementation of dynamic polyphonic fundamental 
% frequency (multi-F0) tracking based on harmonic summation, sub-bin peak
% detection, Kalman filtering, Hungarian assignment, and ghost detection.
%
%
% REQUIREMENTS:
%   - MATLAB R2020a or later recommended
%   - Signal Processing Toolbox = required
%   - Audio Toolbox = optional (for enhanced features)
%   - Optimization Toolbox = optional (for advanced assignment)
%   - Statistics and Machine Learning Toolbox = optional
%
% USAGE:
%   1. Place your .wav file in the same directory or provide full path
%   2. Run this script
%   3. View visualizations and exported results
%
% =========================================================================

%% Clear workspace and set up environment
clear; clc; close all;

% Add all subdirectories to path
addpath(genpath(pwd));

fprintf('==========================================================\n');
fprintf('   DYNAMIC 0-K MULTI-F0 TRACKING SYSTEM\n');
fprintf('   Research Prototype Implementation\n');
fprintf('==========================================================\n\n');

%% Configuration Parameters
% -------------------------------------------------------------------------
% All tunable parameters are centralized here for easy experimentation
% -------------------------------------------------------------------------

config = struct();

% Audio Processing Parameters
config.audio.targetFs = 44100;       % Target sample rate (will resample if different)
config.audio.monoMix = true;         % Convert stereo to mono

% Spectrogram / STFT Parameters
config.stft.windowLength = 2048;     % Window length in samples (~46ms at 44.1kHz)
config.stft.hopLength = 512;         % Hop size in samples (~11.6ms at 44.1kHz)
config.stft.nfft = 4096;             % FFT size (zero-padding for freq resolution)
config.stft.windowType = 'hann';     % Window type: 'hann', 'hamming', 'blackman'

% Salience Function Parameters
config.salience.f0Min = 50;          % Minimum F0 to consider (Hz)
config.salience.f0Max = 2000;        % Maximum F0 to consider (Hz)
config.salience.f0Resolution = 1;    % F0 resolution in Hz for salience function
config.salience.numHarmonics = 10;   % Number of harmonics to sum
config.salience.harmonicWeights = 'energy';  % 'energy', 'linear', 'equal', 'perceptual', 'klapuri'
config.salience.useAuditoryWeighting = true; % Apply A-weighting approximation

% Salience Method Selection (NEW)
% Options: 'stft' (default), 'cwt', 'wavelet', 'cqt', 'ensemble'
config.salience.method = 'stft';

% CWT/Wavelet Salience Parameters (when method = 'cwt' or 'wavelet')
config.wavelet.enabled = false;      % Set true to use CWT-based salience
config.wavelet.waveletType = 'morse'; % 'morse', 'amor' (Morlet), 'bump'
config.wavelet.voicesPerOctave = 48; % Frequency resolution (higher = finer)
config.wavelet.timeBandwidth = 60;   % Morse wavelet time-bandwidth product
config.wavelet.f0Resolution = 10;    % F0 resolution in cents (log spacing)

% Perceptual Weighting Parameters (NEW)
config.perceptual.enabled = true;    % Apply perceptual weighting to salience
config.perceptual.method = 'combined'; % 'loudness', 'equal_loudness', 'masking', 'combined'
config.perceptual.loudnessModel = 'psychoacoustic'; % 'psychoacoustic', 'zwicker', 'custom'
config.perceptual.equalLoudness = true;  % Apply ISO 226 equal-loudness contours
config.perceptual.maskingModel = 'simultaneous'; % 'simultaneous', 'temporal', 'both'
config.perceptual.combineMethod = 'multiply'; % 'multiply', 'weighted_sum'

% Peak Detection Parameters
config.peaks.minProminence = 0.1;    % Minimum peak prominence (normalized)
config.peaks.minDistance = 20;       % Minimum distance between peaks in Hz
config.peaks.maxPeaksPerFrame = 8;   % Maximum number of peaks to detect
config.peaks.subBinInterp = true;    % Enable parabolic sub-bin interpolation
config.peaks.minSalience = 0.05;     % Minimum salience threshold

% Multi-Voice Tracking Parameters
config.tracking.maxVoices = 6;       % Maximum simultaneous voices to track
config.tracking.assignmentThreshold = 100;  % Max frequency diff for assignment (Hz)
config.tracking.minTrackLength = 3;  % Minimum frames for a valid track
config.tracking.maxMissedFrames = 5; % Frames without detection before track death
config.tracking.processNoise = 10;   % Kalman filter process noise (Hz^2)
config.tracking.measurementNoise = 25; % Kalman filter measurement noise (Hz^2)
config.tracking.velocityModel = true; % Use constant-velocity model

% Ghost/Overtone Detection Parameters
config.ghost.enabled = true;         % Enable ghost detection
config.ghost.harmonicTolerance = 0.03;  % Tolerance for harmonic ratio (3%)
config.ghost.minEnergyratio = 0.3;   % Min energy ratio to be considered real
config.ghost.checkCombinations = true;  % Check for combination tones

% Visualization Parameters
config.viz.showSpectrogram = true;
config.viz.showSalience = true;
config.viz.showTracks = true;
config.viz.colormap = 'parula';
config.viz.figureSize = [1400, 900];

% Export Parameters
config.export.saveResults = true;
config.export.outputDir = 'results';
config.export.formats = {'mat', 'csv'};

%% Load Audio File
% -------------------------------------------------------------------------
% Supports standard WAV files (and any format audioread supports)
% -------------------------------------------------------------------------

fprintf('Loading audio file...\n');

% Try to find a .wav file in the current directory, or use a default
wavFiles = dir('*.wav');
if ~isempty(wavFiles)
    audioFile = "_tag.wav";
    fprintf('  Found: %s\n', audioFile);
else
    % Create a synthetic test signal if no audio file available
    fprintf('  No .wav file found. Generating synthetic polyphonic test signal...\n');
    audioFile = 'synthetic_test.wav';
    generateTestSignal(audioFile, config.audio.targetFs);
end

try
    [audioData, fs] = audioread(audioFile);
    fprintf('  Sample rate: %d Hz\n', fs);
    fprintf('  Duration: %.2f seconds\n', size(audioData, 1) / fs);
    fprintf('  Channels: %d\n', size(audioData, 2));
catch ME
    error('Failed to load audio file: %s\n%s', audioFile, ME.message);
end

%% Preprocess Audio
% -------------------------------------------------------------------------
fprintf('\nPreprocessing audio...\n');

% Convert to mono if stereo
if size(audioData, 2) > 1 && config.audio.monoMix
    audioData = mean(audioData, 2);
    fprintf('  Converted to mono\n');
end

% Resample if necessary
if fs ~= config.audio.targetFs
    fprintf('  Resampling from %d Hz to %d Hz...\n', fs, config.audio.targetFs);
    audioData = resample(audioData, config.audio.targetFs, fs);
    fs = config.audio.targetFs;
end

% Normalize audio
audioData = audioData / max(abs(audioData) + eps);
fprintf('  Normalized amplitude\n');

% High-pass filter to remove DC and very low frequencies
[b, a] = butter(2, 30 / (fs/2), 'high');
audioData = filtfilt(b, a, audioData);
fprintf('  Applied high-pass filter (30 Hz cutoff)\n');

%% Compute Spectrogram
% -------------------------------------------------------------------------
fprintf('\nComputing STFT/Spectrogram...\n');

[S, freqBins, timeFrames, stftComplex] = computeSpectrogram(audioData, fs, config.stft);

fprintf('  Frequency bins: %d (%.1f Hz - %.1f Hz)\n', length(freqBins), freqBins(1), freqBins(end));
fprintf('  Time frames: %d (%.3f s frame hop)\n', length(timeFrames), config.stft.hopLength/fs);

%% Compute Salience Function
% -------------------------------------------------------------------------
fprintf('\nComputing salience function...\n');

% Select salience computation method
switch lower(config.salience.method)
    case {'cwt', 'wavelet'}
        % CWT-based salience (Wavelet Toolbox)
        fprintf('  Using CWT-based salience computation (Wavelet Toolbox)...\n');
        
        waveletParams = struct();
        waveletParams.f0Min = config.salience.f0Min;
        waveletParams.f0Max = config.salience.f0Max;
        waveletParams.f0Resolution = config.wavelet.f0Resolution;
        waveletParams.waveletType = config.wavelet.waveletType;
        waveletParams.voicesPerOctave = config.wavelet.voicesPerOctave;
        waveletParams.timeBandwidth = config.wavelet.timeBandwidth;
        waveletParams.numHarmonics = config.salience.numHarmonics;
        waveletParams.harmonicWeights = config.salience.harmonicWeights;
        
        [salience, f0Candidates, waveletInfo] = computeSalienceWavelet(audioData, fs, waveletParams);
        
    case 'cqt'
        % CQT-based salience (from computeSalienceAdvanced)
        fprintf('  Using CQT-based salience computation...\n');
        [salience, f0Candidates] = computeSalienceAdvanced(S, freqBins, config.salience, 'cqt', audioData, fs);
        
    case 'ensemble'
        % Ensemble method (combine multiple approaches)
        fprintf('  Using ensemble salience computation...\n');
        [salience, f0Candidates] = computeSalienceAdvanced(S, freqBins, config.salience, 'ensemble', audioData, fs);
        
    otherwise
        % Default STFT-based harmonic summation
        fprintf('  Using STFT-based harmonic summation...\n');
        [salience, f0Candidates] = computeSalience(S, freqBins, config.salience);
end

fprintf('  F0 candidates: %d (%.1f Hz - %.1f Hz)\n', ...
    length(f0Candidates), f0Candidates(1), f0Candidates(end));
fprintf('  Salience matrix size: %d x %d\n', size(salience, 1), size(salience, 2));

%% Apply Perceptual Weighting (NEW)
% -------------------------------------------------------------------------
if config.perceptual.enabled
    fprintf('\nApplying perceptual weighting...\n');
    
    perceptualParams = struct();
    perceptualParams.method = config.perceptual.method;
    perceptualParams.loudnessModel = config.perceptual.loudnessModel;
    perceptualParams.equalLoudness = config.perceptual.equalLoudness;
    perceptualParams.maskingModel = config.perceptual.maskingModel;
    perceptualParams.combineMethod = config.perceptual.combineMethod;
    perceptualParams.frameLength = config.stft.windowLength;
    perceptualParams.hopLength = config.stft.hopLength;
    
    [salience, perceptualInfo] = computePerceptualWeights(salience, f0Candidates, audioData, fs, perceptualParams);
    
    fprintf('  Perceptual weighting applied (method: %s)\n', config.perceptual.method);
end

%% Detect Peaks with Sub-bin Interpolation
% -------------------------------------------------------------------------
fprintf('\nDetecting peaks with sub-bin interpolation...\n');

[detections, peakInfo] = detectPeaks(salience, f0Candidates, config.peaks);

totalDetections = sum(cellfun(@length, {detections.frequencies}));
fprintf('  Total detections across all frames: %d\n', totalDetections);
fprintf('  Average detections per frame: %.2f\n', totalDetections / length(detections));

%% Ghost / Overtone Detection
% -------------------------------------------------------------------------
if config.ghost.enabled
    fprintf('\nIdentifying ghost tones and overtones...\n');
    [detections, ghostInfo] = identifyGhosts(detections, S, freqBins, config.ghost);
    fprintf('  Ghost/overtone candidates flagged: %d\n', ghostInfo.totalFlagged);
end

%% Multi-Voice Tracking with Kalman Filtering
% -------------------------------------------------------------------------
fprintf('\nPerforming multi-voice tracking...\n');

[tracks, trackingInfo] = trackMultipleVoices(detections, timeFrames, config.tracking);

fprintf('  Total tracks created: %d\n', length(tracks));
fprintf('  Valid tracks (>%d frames): %d\n', config.tracking.minTrackLength, ...
    sum([tracks.length] >= config.tracking.minTrackLength));

% Filter out short tracks
validTracks = tracks([tracks.length] >= config.tracking.minTrackLength);
fprintf('  Retained %d valid tracks\n', length(validTracks));

%% Post-Processing: Smooth Tracks
% -------------------------------------------------------------------------
fprintf('\nPost-processing tracks...\n');

for i = 1:length(validTracks)
    % Apply median filter to remove outliers
    if length(validTracks(i).frequencies) >= 5
        validTracks(i).smoothedFreqs = medfilt1(validTracks(i).frequencies, 5);
    else
        validTracks(i).smoothedFreqs = validTracks(i).frequencies;
    end
end
fprintf('  Applied median smoothing to tracks\n');

%% Visualization
% -------------------------------------------------------------------------
fprintf('\nGenerating visualizations...\n');

% Create main figure
mainFig = figure('Name', 'Multi-F0 Tracking Results', ...
    'Position', [50, 50, config.viz.figureSize], ...
    'Color', 'w');

% Subplot 1: Spectrogram with tracked F0s
subplot(3, 2, [1, 2]);
visualizeSpectrumWithTracks(S, freqBins, timeFrames, validTracks, config);
title('Spectrogram with Tracked F0 Contours', 'FontSize', 14, 'FontWeight', 'bold');

% Subplot 2: Salience Function
subplot(3, 2, 3);
visualizeSalience(salience, f0Candidates, timeFrames, config);
title('Salience Function', 'FontSize', 12, 'FontWeight', 'bold');

% Subplot 3: Detected Peaks Over Time
subplot(3, 2, 4);
visualizeDetections(detections, timeFrames, config);
title('Raw Peak Detections', 'FontSize', 12, 'FontWeight', 'bold');

% Subplot 4: Track Summary
subplot(3, 2, 5);
visualizeTrackSummary(validTracks, timeFrames);
title('Track Duration Summary', 'FontSize', 12, 'FontWeight', 'bold');

% Subplot 5: Tracking Statistics
subplot(3, 2, 6);
visualizeTrackingStats(trackingInfo, validTracks);
title('Tracking Statistics', 'FontSize', 12, 'FontWeight', 'bold');

% Adjust layout
sgtitle('Dynamic 0-K Multi-F0 Tracking Analysis', 'FontSize', 16, 'FontWeight', 'bold');

%% Create Detailed Track Visualization
% -------------------------------------------------------------------------
detailFig = figure('Name', 'Detailed F0 Tracks', ...
    'Position', [100, 100, 1200, 600], ...
    'Color', 'w');

% Plot each track with confidence intervals
hold on;
colors = lines(length(validTracks));
legendEntries = cell(length(validTracks), 1);

for i = 1:length(validTracks)
    track = validTracks(i);
    t = timeFrames(track.frameIndices);
    f = track.smoothedFreqs;
    
    % Plot confidence band (based on Kalman covariance if available)
    if isfield(track, 'covariances') && ~isempty(track.covariances)
        stdDev = sqrt(track.covariances);
        fill([t, fliplr(t)], [f-2*stdDev, fliplr(f+2*stdDev)], ...
            colors(i,:), 'FaceAlpha', 0.2, 'EdgeColor', 'none');
    end
    
    % Plot main track
    plot(t, f, '-', 'Color', colors(i,:), 'LineWidth', 2);
    
    % Mark track start and end
    plot(t(1), f(1), 'o', 'Color', colors(i,:), 'MarkerSize', 8, 'MarkerFaceColor', colors(i,:));
    plot(t(end), f(end), 's', 'Color', colors(i,:), 'MarkerSize', 8, 'MarkerFaceColor', colors(i,:));
    
    legendEntries{i} = sprintf('Voice %d (%.1f-%.1f Hz)', i, min(f), max(f));
end

hold off;
xlabel('Time (s)', 'FontSize', 12);
ylabel('Frequency (Hz)', 'FontSize', 12);
title('Tracked F0 Contours with Confidence Intervals', 'FontSize', 14, 'FontWeight', 'bold');
legend(legendEntries, 'Location', 'best');
grid on;
set(gca, 'YScale', 'log');
ylim([config.salience.f0Min, config.salience.f0Max]);

%% Export Results
% -------------------------------------------------------------------------
if config.export.saveResults
    fprintf('\nExporting results...\n');
    
    % Create output directory
    if ~exist(config.export.outputDir, 'dir')
        mkdir(config.export.outputDir);
    end
    
    % Prepare results structure
    results = struct();
    results.config = config;
    results.audioFile = audioFile;
    results.sampleRate = fs;
    results.timeFrames = timeFrames;
    results.f0Candidates = f0Candidates;
    results.salience = salience;
    results.detections = detections;
    results.tracks = validTracks;
    results.trackingInfo = trackingInfo;
    
    % Save as MAT file
    if ismember('mat', config.export.formats)
        matFile = fullfile(config.export.outputDir, 'multiF0_results.mat');
        save(matFile, 'results', '-v7.3');
        fprintf('  Saved: %s\n', matFile);
    end
    
    % Save tracks as CSV
    if ismember('csv', config.export.formats)
        csvFile = fullfile(config.export.outputDir, 'tracked_pitches.csv');
        exportTracksToCSV(validTracks, timeFrames, csvFile);
        fprintf('  Saved: %s\n', csvFile);
    end
    
    % Save figures
    figFile1 = fullfile(config.export.outputDir, 'multiF0_overview.png');
    exportgraphics(mainFig, figFile1, 'Resolution', 300);
    fprintf('  Saved: %s\n', figFile1);
    
    figFile2 = fullfile(config.export.outputDir, 'f0_tracks_detail.png');
    exportgraphics(detailFig, figFile2, 'Resolution', 300);
    fprintf('  Saved: %s\n', figFile2);
end

%% Print Summary
% -------------------------------------------------------------------------
fprintf('\n==========================================================\n');
fprintf('   ANALYSIS COMPLETE\n');
fprintf('==========================================================\n\n');

fprintf('Summary:\n');
fprintf('  Audio duration: %.2f seconds\n', timeFrames(end));
fprintf('  Analysis frames: %d\n', length(timeFrames));
fprintf('  Valid voice tracks: %d\n', length(validTracks));

if ~isempty(validTracks)
    fprintf('\nTrack Details:\n');
    for i = 1:length(validTracks)
        track = validTracks(i);
        fprintf('  Track %d: %.1f Hz - %.1f Hz, duration: %.2f s\n', ...
            i, min(track.frequencies), max(track.frequencies), ...
            timeFrames(track.frameIndices(end)) - timeFrames(track.frameIndices(1)));
    end
end

fprintf('\n');

%% =========================================================================
% HELPER FUNCTIONS
% =========================================================================

function generateTestSignal(filename, fs)
    % Generate a synthetic polyphonic test signal
    duration = 5; % seconds
    t = (0:1/fs:duration-1/fs)';
    
    % Create multiple overlapping tones with varying frequencies
    signal = zeros(size(t));
    
    % Voice 1: Steady tone at ~220 Hz (A3)
    f1 = 220;
    env1 = [zeros(round(0.2*fs), 1); ones(round(3*fs), 1); zeros(round(1.8*fs), 1)];
    env1 = env1(1:length(t));
    signal = signal + 0.4 * env1 .* sin(2*pi*f1*t);
    
    % Voice 2: Gliding tone from 330 Hz to 440 Hz (E4 to A4)
    f2_start = 330; f2_end = 440;
    f2 = linspace(f2_start, f2_end, length(t))';
    env2 = [zeros(round(0.5*fs), 1); ones(round(2.5*fs), 1); zeros(round(2*fs), 1)];
    env2 = env2(1:length(t));
    phase2 = cumsum(2*pi*f2/fs);
    signal = signal + 0.35 * env2 .* sin(phase2);
    
    % Voice 3: Short note at 523 Hz (C5)
    f3 = 523;
    env3 = [zeros(round(1*fs), 1); ones(round(1*fs), 1); zeros(round(3*fs), 1)];
    env3 = env3(1:length(t));
    signal = signal + 0.3 * env3 .* sin(2*pi*f3*t);
    
    % Voice 4: Vibrato tone around 660 Hz (E5)
    f4_center = 660;
    vibRate = 5; % Hz
    vibDepth = 10; % Hz
    f4 = f4_center + vibDepth * sin(2*pi*vibRate*t);
    env4 = [zeros(round(2*fs), 1); ones(round(2*fs), 1); zeros(round(1*fs), 1)];
    env4 = env4(1:length(t));
    phase4 = cumsum(2*pi*f4/fs);
    signal = signal + 0.25 * env4 .* sin(phase4);
    
    % Add harmonics to make it more realistic
    for h = 2:6
        harmAmp = 0.5 / h;
        signal = signal + harmAmp * 0.4 * env1 .* sin(2*pi*h*f1*t);
        signal = signal + harmAmp * 0.35 * env2 .* sin(h*phase2);
        signal = signal + harmAmp * 0.3 * env3 .* sin(2*pi*h*f3*t);
        signal = signal + harmAmp * 0.25 * env4 .* sin(h*phase4);
    end
    
    % Normalize and add slight noise
    signal = signal / max(abs(signal));
    signal = signal + 0.01 * randn(size(signal));
    signal = signal * 0.9;
    
    % Save
    audiowrite(filename, signal, fs);
    fprintf('    Generated %s (%.1f seconds, %d Hz)\n', filename, duration, fs);
end

function exportTracksToCSV(tracks, timeFrames, filename)
    % Export tracks to CSV format
    % Each row: time, voice1_freq, voice2_freq, ... (NaN for inactive)
    
    numFrames = length(timeFrames);
    numTracks = length(tracks);
    
    % Create data matrix
    data = NaN(numFrames, numTracks + 1);
    data(:, 1) = timeFrames(:);
    
    for i = 1:numTracks
        track = tracks(i);
        data(track.frameIndices, i + 1) = track.frequencies;
    end
    
    % Create header
    headers = ['Time_s', arrayfun(@(x) sprintf('Voice%d_Hz', x), 1:numTracks, 'UniformOutput', false)];
    
    % Write to file
    fid = fopen(filename, 'w');
    fprintf(fid, '%s\n', strjoin(headers, ','));
    fclose(fid);
    dlmwrite(filename, data, '-append', 'precision', '%.4f');
end

function visualizeSpectrumWithTracks(S, freqBins, timeFrames, tracks, config)
    % Visualize spectrogram with overlaid tracks
    
    % Plot spectrogram (log scale for better visualization)
    S_dB = 20*log10(S + eps);
    S_dB = S_dB - max(S_dB(:));  % Normalize to 0 dB max
    
    imagesc(timeFrames, freqBins, S_dB);
    axis xy;
    colormap(config.viz.colormap);
    colorbar;
    caxis([-80, 0]);
    
    hold on;
    
    % Overlay tracks
    colors = lines(length(tracks));
    for i = 1:length(tracks)
        track = tracks(i);
        t = timeFrames(track.frameIndices);
        f = track.smoothedFreqs;
        plot(t, f, '-', 'Color', colors(i,:), 'LineWidth', 2.5);
    end
    
    hold off;
    
    xlabel('Time (s)', 'FontSize', 11);
    ylabel('Frequency (Hz)', 'FontSize', 11);
    ylim([config.salience.f0Min, min(config.salience.f0Max * 2, freqBins(end))]);
end

function visualizeSalience(salience, f0Candidates, timeFrames, ~)
    % Visualize salience function
    imagesc(timeFrames, f0Candidates, salience);
    axis xy;
    colormap(gca, 'hot');
    colorbar;
    xlabel('Time (s)', 'FontSize', 11);
    ylabel('F0 Candidate (Hz)', 'FontSize', 11);
end

function visualizeDetections(detections, timeFrames, ~)
    % Visualize raw detections
    hold on;
    for i = 1:length(detections)
        t = timeFrames(i);
        freqs = detections(i).frequencies;
        sals = detections(i).saliences;
        
        % Scale marker size by salience
        for j = 1:length(freqs)
            markerSize = 5 + 20 * sals(j);
            plot(t, freqs(j), '.', 'MarkerSize', markerSize, 'Color', [0.2, 0.4, 0.8]);
        end
    end
    hold off;
    xlabel('Time (s)', 'FontSize', 11);
    ylabel('Detected Frequency (Hz)', 'FontSize', 11);
    set(gca, 'YScale', 'log');
end

function visualizeTrackSummary(tracks, timeFrames)
    % Visualize track durations
    numTracks = length(tracks);
    
    if numTracks == 0
        text(0.5, 0.5, 'No tracks detected', 'HorizontalAlignment', 'center');
        return;
    end
    
    hold on;
    colors = lines(numTracks);
    for i = 1:numTracks
        track = tracks(i);
        startTime = timeFrames(track.frameIndices(1));
        endTime = timeFrames(track.frameIndices(end));
        avgFreq = mean(track.frequencies);
        
        % Draw horizontal bar
        barh(i, endTime - startTime, 0.6, 'FaceColor', colors(i,:), 'BaseValue', startTime);
    end
    hold off;
    
    xlabel('Time (s)', 'FontSize', 11);
    ylabel('Track Number', 'FontSize', 11);
    yticks(1:numTracks);
    xlim([0, timeFrames(end)]);
end

function visualizeTrackingStats(trackingInfo, tracks)
    % Visualize tracking statistics as text
    
    % Clear axes and use as text display
    axis off;
    
    stats = {
        sprintf('Tracking Statistics:');
        sprintf('');
        sprintf('Total frames analyzed: %d', trackingInfo.totalFrames);
        sprintf('Total detections: %d', trackingInfo.totalDetections);
        sprintf('Total tracks created: %d', trackingInfo.totalTracksCreated);
        sprintf('Valid tracks retained: %d', length(tracks));
        sprintf('');
        sprintf('Average track length: %.1f frames', mean([tracks.length]));
        sprintf('Max simultaneous voices: %d', trackingInfo.maxSimultaneous);
        sprintf('Track births: %d', trackingInfo.births);
        sprintf('Track deaths: %d', trackingInfo.deaths);
    };
    
    text(0.1, 0.9, stats, 'VerticalAlignment', 'top', 'FontSize', 10, ...
        'FontName', 'FixedWidth', 'Units', 'normalized');
end
