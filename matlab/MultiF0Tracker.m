classdef MultiF0Tracker < handle
    % MULTIF0TRACKER Dynamic 0-K Multi-F0 Tracker for A Cappella Vocal Ensembles
    %
    % Tracks 0-K simultaneous sung pitches with consistent voice identity,
    % automatic entry/exit detection, and "ghost pitch" identification
    % (barbershop fifth voice, Sardinian quintina).
    %
    % Usage:
    %   tracker = MultiF0Tracker(MaxVoices=4, MinFreq=80);
    %   result = tracker.track(audio, sr);
    %   result.visualize();
    %
    % Author: Jordan Lenchitz

    properties
        % Audio parameters
        SampleRate (1,1) double {mustBePositive} = 22050
        HopLength (1,1) double {mustBePositive, mustBeInteger} = 512
        FrameLength (1,1) double {mustBePositive, mustBeInteger} = 4096
        
        % Pitch detection
        MinFreq (1,1) double {mustBePositive} = 65
        MaxFreq (1,1) double {mustBePositive} = 1400
        MaxVoices (1,1) double {mustBePositive, mustBeInteger} = 8
        PeakThreshold (1,1) double {mustBeInRange(PeakThreshold, 0, 1)} = 0.1
        
        % Tracking
        MaxPitchJumpCents (1,1) double {mustBePositive} = 300
        TentativeFrames (1,1) double {mustBePositive, mustBeInteger} = 3
        InactiveFrames (1,1) double {mustBePositive, mustBeInteger} = 5
        
        % Ghost pitch detection
        DetectExtraPitches (1,1) logical = true
        CombinationToneTolerance (1,1) double {mustBePositive} = 30
        OvertoneTolerance (1,1) double {mustBePositive} = 20
    end
    
    properties (Access = private)
        Tracks (:,1) cell = {}
        NextTrackId (1,1) double = 1
    end
    
    properties (Constant, Hidden)
        STATE_TENTATIVE = 1
        STATE_ACTIVE = 2
        STATE_TERMINATED = 3
    end

    methods
        function obj = MultiF0Tracker(options)
            % Constructor with name-value arguments
            arguments
                options.SampleRate = 22050
                options.HopLength = 512
                options.FrameLength = 4096
                options.MinFreq = 65
                options.MaxFreq = 1400
                options.MaxVoices = 8
                options.PeakThreshold = 0.1
                options.MaxPitchJumpCents = 300
                options.TentativeFrames = 3
                options.InactiveFrames = 5
                options.DetectExtraPitches = true
                options.CombinationToneTolerance = 30
                options.OvertoneTolerance = 20
            end
            
            fields = fieldnames(options);
            for i = 1:numel(fields)
                obj.(fields{i}) = options.(fields{i});
            end
        end

        function result = track(obj, audio, sr)
            % TRACK Track all voices in an audio signal
            arguments
                obj
                audio (:,:) double
                sr (1,1) double {mustBePositive}
            end
            
            % Ensure mono
            if width(audio) > 1
                audio = mean(audio, 2);
            end
            
            % Resample if needed
            if sr ~= obj.SampleRate
                audio = resample(audio, obj.SampleRate, sr);
                sr = obj.SampleRate;
            end
            
            % Reset state
            obj.Tracks = {};
            obj.NextTrackId = 1;
            
            % STFT setup
            win = hann(obj.FrameLength, "periodic");
            nFrames = floor((numel(audio) - obj.FrameLength) / obj.HopLength) + 1;
            freqs = (0:obj.FrameLength/2) * sr / obj.FrameLength;
            times = ((0:nFrames-1) * obj.HopLength + obj.FrameLength/2) / sr;
            
            fprintf("Processing %d frames...\n", nFrames);
            
            % Process frames
            for frame = 1:nFrames
                idx = (frame-1) * obj.HopLength + (1:obj.FrameLength);
                if idx(end) > numel(audio), break; end
                
                spectrum = abs(fft(audio(idx) .* win));
                spectrum = spectrum(1:obj.FrameLength/2+1);
                
                [f0s, sal] = obj.computeSalience(spectrum, freqs);
                peaks = obj.detectPeaks(f0s, sal);
                obj.updateTracks(peaks, frame);
                
                if mod(frame, 100) == 0
                    fprintf("  Frame %d/%d\n", frame, nFrames);
                end
            end
            
            % Post-process
            obj.smoothTracks();
            
            % Separate voices from ghosts
            [sungVoices, extraPitches] = obj.separateTracks();
            
            % Build result object
            result = TrackingResult(times, sungVoices, extraPitches, sr, obj.HopLength);
            
            fprintf("Done: %d voices, %d ghost pitches\n", numel(sungVoices), numel(extraPitches));
        end
    end

    methods (Access = private)
        function [f0s, salience] = computeSalience(obj, spectrum, freqs)
            nBins = 500;
            f0s = logspace(log10(obj.MinFreq), log10(obj.MaxFreq), nBins);
            salience = zeros(1, nBins);
            
            weights = [1.0, 0.8, 0.6, 0.5, 0.4, 0.3];
            
            for i = 1:nBins
                total = 0;
                for h = 1:6
                    fh = f0s(i) * h;
                    if fh > freqs(end), break; end
                    [~, idx] = min(abs(freqs - fh));
                    rng = max(1, idx-3):min(numel(spectrum), idx+3);
                    total = total + weights(h) * max(spectrum(rng));
                end
                salience(i) = total;
            end
            
            salience = salience / max(salience, [], "all", "omitmissing");
        end

        function peaks = detectPeaks(obj, freqs, salience)
            [pks, locs] = findpeaks(salience, MinPeakHeight=obj.PeakThreshold, MinPeakProminence=0.05);
            
            peaks = zeros(numel(locs), 2);
            for i = 1:numel(locs)
                idx = locs(i);
                if idx > 1 && idx < numel(salience)
                    % Parabolic interpolation
                    a = salience(idx-1); b = salience(idx); c = salience(idx+1);
                    offset = 0.5 * (a - c) / (a - 2*b + c + 1e-10);
                    peaks(i,:) = [interp1(1:numel(freqs), freqs, idx + offset), pks(i)];
                else
                    peaks(i,:) = [freqs(idx), pks(i)];
                end
            end
            
            if ~isempty(peaks)
                [~, ord] = sort(peaks(:,2), "descend");
                peaks = peaks(ord(1:min(end, obj.MaxVoices*2)), :);
            end
        end

        function updateTracks(obj, peaks, frame)
            % Get active track indices
            activeIdx = find(cellfun(@(t) t.State ~= obj.STATE_TERMINATED && ~t.IsExtra, obj.Tracks));
            nTracks = numel(activeIdx);
            nPeaks = size(peaks, 1);
            
            if nTracks == 0 && nPeaks == 0, return; end
            
            % Start new tracks if none exist
            if nTracks == 0
                for j = 1:min(nPeaks, obj.MaxVoices)
                    if peaks(j,2) > obj.PeakThreshold
                        obj.createTrack(frame, peaks(j,1), peaks(j,2), false);
                    end
                end
                return;
            end
            
            % Mark all inactive if no peaks
            if nPeaks == 0
                for i = activeIdx'
                    obj.Tracks{i}.InactiveCount = obj.Tracks{i}.InactiveCount + 1;
                    if obj.Tracks{i}.InactiveCount >= obj.InactiveFrames
                        obj.Tracks{i}.State = obj.STATE_TERMINATED;
                    end
                end
                return;
            end
            
            % Build cost matrix
            costMat = 1e6 * ones(nTracks, nPeaks);
            for i = 1:nTracks
                lastF0 = obj.Tracks{activeIdx(i)}.Pitches(end);
                for j = 1:nPeaks
                    cents = abs(1200 * log2(peaks(j,1) / lastF0));
                    if cents <= obj.MaxPitchJumpCents
                        costMat(i,j) = cents;
                    end
                end
            end
            
            % Hungarian assignment
            M = matchpairs(costMat, 1e5);
            assigned = false(nPeaks, 1);
            assignedTracks = false(nTracks, 1);
            
            for k = 1:size(M, 1)
                i = M(k,1); j = M(k,2);
                if costMat(i,j) < 1e5
                    tIdx = activeIdx(i);
                    obj.Tracks{tIdx}.Frames(end+1) = frame;
                    obj.Tracks{tIdx}.Pitches(end+1) = peaks(j,1);
                    obj.Tracks{tIdx}.Confidences(end+1) = peaks(j,2);
                    obj.Tracks{tIdx}.InactiveCount = 0;
                    
                    if obj.Tracks{tIdx}.State == obj.STATE_TENTATIVE
                        obj.Tracks{tIdx}.TentativeCount = obj.Tracks{tIdx}.TentativeCount + 1;
                        if obj.Tracks{tIdx}.TentativeCount >= obj.TentativeFrames
                            obj.Tracks{tIdx}.State = obj.STATE_ACTIVE;
                        end
                    end
                    assigned(j) = true;
                    assignedTracks(i) = true;
                end
            end
            
            % Update unassigned tracks
            for i = find(~assignedTracks)'
                tIdx = activeIdx(i);
                obj.Tracks{tIdx}.InactiveCount = obj.Tracks{tIdx}.InactiveCount + 1;
                if obj.Tracks{tIdx}.InactiveCount >= obj.InactiveFrames
                    obj.Tracks{tIdx}.State = obj.STATE_TERMINATED;
                end
            end
            
            % Handle unassigned peaks
            nActive = sum(cellfun(@(t) t.State ~= obj.STATE_TERMINATED && ~t.IsExtra, obj.Tracks));
            for j = find(~assigned)'
                if peaks(j,2) > obj.PeakThreshold * 1.2
                    isGhost = obj.DetectExtraPitches && obj.isCombinationTone(peaks(j,1), peaks(assigned,1));
                    if isGhost
                        obj.createTrack(frame, peaks(j,1), peaks(j,2), true);
                    elseif nActive < obj.MaxVoices
                        obj.createTrack(frame, peaks(j,1), peaks(j,2), false);
                        nActive = nActive + 1;
                    end
                end
            end
        end

        function createTrack(obj, frame, pitch, conf, isExtra)
            track = struct( ...
                Id=obj.NextTrackId, StartFrame=frame, Frames=frame, ...
                Pitches=pitch, Confidences=conf, State=obj.STATE_TENTATIVE, ...
                InactiveCount=0, TentativeCount=1, IsExtra=isExtra);
            obj.Tracks{end+1} = track;
            obj.NextTrackId = obj.NextTrackId + 1;
        end

        function isGhost = isCombinationTone(obj, pitch, sungFreqs)
            isGhost = false;
            if numel(sungFreqs) < 2, return; end
            
            for i = 1:numel(sungFreqs)
                for j = i+1:numel(sungFreqs)
                    f1 = sungFreqs(i); f2 = sungFreqs(j);
                    combos = [abs(f2-f1), 2*f1-f2, 2*f2-f1];
                    if any(abs(1200*log2(pitch./combos)) < obj.CombinationToneTolerance)
                        isGhost = true; return;
                    end
                end
                % Check overtones
                for h = 2:4
                    if abs(1200*log2(pitch/(sungFreqs(i)*h))) < obj.OvertoneTolerance
                        isGhost = true; return;
                    end
                end
            end
        end

        function smoothTracks(obj)
            for i = 1:numel(obj.Tracks)
                if numel(obj.Tracks{i}.Pitches) >= 3
                    obj.Tracks{i}.Pitches = smoothdata(obj.Tracks{i}.Pitches, "gaussian", 3);
                end
            end
        end

        function [voices, ghosts] = separateTracks(obj)
            voices = {}; ghosts = {};
            for i = 1:numel(obj.Tracks)
                t = obj.Tracks{i};
                if numel(t.Pitches) >= obj.TentativeFrames
                    if t.IsExtra
                        ghosts{end+1} = t;
                    else
                        voices{end+1} = t;
                    end
                end
            end
        end
    end
end
