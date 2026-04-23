classdef AffordanceField < handle
    % AffordanceField  spectral affordance field for a cappella listening.
    %
    % the competition-model tracker asks "which partials win?" this class asks
    % "where does the sound invite spectral listening, and how strongly?"
    %
    % the field A(t, f) is the product of two parts:
    %
    %   peripheral availability  ·  what the auditory periphery permits
    %     - energy above the local masking threshold
    %     - weighting by the dominance region (ritsma 1967: 500 to 2000 hz)
    %     - critical band smoothing (equivalent rectangular bandwidth scale)
    %
    %   affordance features  ·  what the local sound structure offers
    %     - presence        is there something here to hear right now
    %     - persistence     has there been something here i could still track
    %     - continuity      does this connect to what came just before
    %     - change          did something new arrive that could recruit attention
    %     - harmonic coherence  does this region resemble a voice or timbre
    %
    % this first pass implements presence, persistence, continuity, and change.
    % harmonic coherence is provided as a stub that returns ones, to be filled
    % in by a later revision.
    %
    % usage:
    %   field = AffordanceField(SampleRate=22050);
    %   A = field.compute(audio);
    %   field.visualize(A);
    %
    % the field does not predict what any listener will hear. it articulates
    % the structure of possibilities the sound offers. la quintina is not
    % detected by A. la quintina is enacted by a listener who takes up an
    % affordance that A makes visible.

    properties
        SampleRate (1,1) double {mustBePositive} = 22050
        FrameLength (1,1) double {mustBePositive, mustBeInteger} = 4096
        HopLength (1,1) double {mustBePositive, mustBeInteger} = 512

        % masking parameters
        MaskingFloorDb (1,1) double = -60    % global noise floor
        MaskingSpreadErb (1,1) double = 1.5  % spread of simultaneous masking in erb units

        % dominance region (ritsma 1967)
        DominanceLowHz (1,1) double = 500
        DominanceHighHz (1,1) double = 2000
        DominanceWeight (1,1) double = 1.0   % additional weight inside the region

        % persistence and change time constants, in seconds
        PersistenceTau (1,1) double = 0.4
        ChangeTau (1,1) double = 0.05

        % continuity smoothing in frequency, in equivalent rectangular bandwidth units
        ContinuityErbSigma (1,1) double = 0.5
    end

    methods
        function obj = AffordanceField(options)
            arguments
                options.SampleRate = 22050
                options.FrameLength = 4096
                options.HopLength = 512
                options.MaskingFloorDb = -60
                options.MaskingSpreadErb = 1.5
                options.DominanceLowHz = 500
                options.DominanceHighHz = 2000
                options.DominanceWeight = 1.0
                options.PersistenceTau = 0.4
                options.ChangeTau = 0.05
                options.ContinuityErbSigma = 0.5
            end
            fields = fieldnames(options);
            for i = 1:numel(fields)
                obj.(fields{i}) = options.(fields{i});
            end
        end

        function A = compute(obj, audio)
            % compute the affordance field. returns a struct with the field
            % and each component, so the caller can inspect what drives where.
            arguments
                obj
                audio (:,1) double
            end

            [S, freqs, times] = obj.stft(audio);
            mag = abs(S);
            magDb = 20 * log10(mag + 1e-12);

            availability = obj.peripheralAvailability(magDb, freqs);
            presence = obj.featurePresence(mag);
            persistence = obj.featurePersistence(presence);
            continuity = obj.featureContinuity(presence, freqs);
            change = obj.featureChange(presence);
            coherence = obj.featureHarmonicCoherence(mag, freqs);

            % feature integration. geometric-mean style: all four features
            % weigh in, but any near-zero pulls the result toward zero.
            featureStack = presence .* persistence .* continuity .* change .* coherence;
            featureStack = featureStack .^ (1/5);

            field = availability .* featureStack;

            A = struct( ...
                Field=field, ...
                Availability=availability, ...
                Presence=presence, ...
                Persistence=persistence, ...
                Continuity=continuity, ...
                Change=change, ...
                Coherence=coherence, ...
                Magnitude=mag, ...
                Frequencies=freqs, ...
                Times=times);
        end

        function fig = visualize(obj, A, options)
            % show spectrogram, affordance field, and the four feature maps.
            arguments
                obj
                A struct
                options.OutputPath string = ""
                options.FrequencyLimit (1,2) double = [60, 4000]
                options.Title string = "spectral affordance field"
            end

            fig = figure(Position=[100, 100, 1400, 900], Color="white");
            tl = tiledlayout(3, 2, TileSpacing="compact", Padding="compact");
            title(tl, options.Title, FontSize=16, FontWeight="bold");

            magDb = 20 * log10(A.Magnitude + 1e-12);
            magDb = magDb - max(magDb, [], "all");

            obj.plotHeatmap(A.Times, A.Frequencies, magDb, ...
                "magnitude spectrogram, db from peak", [-80, 0], options.FrequencyLimit);
            obj.plotHeatmap(A.Times, A.Frequencies, A.Field, ...
                "affordance field A(t, f)", [0, max(A.Field, [], "all") * 0.9], options.FrequencyLimit);
            obj.plotHeatmap(A.Times, A.Frequencies, A.Availability, ...
                "peripheral availability", [0, 1], options.FrequencyLimit);
            obj.plotHeatmap(A.Times, A.Frequencies, A.Persistence, ...
                "persistence", [0, 1], options.FrequencyLimit);
            obj.plotHeatmap(A.Times, A.Frequencies, A.Continuity, ...
                "continuity", [0, 1], options.FrequencyLimit);
            obj.plotHeatmap(A.Times, A.Frequencies, A.Change, ...
                "change", [0, 1], options.FrequencyLimit);

            if options.OutputPath ~= ""
                exportgraphics(fig, options.OutputPath, Resolution=300);
                fprintf("figure saved: %s\n", options.OutputPath);
            end
        end
    end

    methods (Access = private)

        function [S, freqs, times] = stft(obj, audio)
            % short-time fourier transform. mirrors the tracker's windowing.
            win = hann(obj.FrameLength, "periodic");
            nFrames = floor((numel(audio) - obj.FrameLength) / obj.HopLength) + 1;
            nBins = obj.FrameLength / 2 + 1;
            S = zeros(nBins, nFrames);
            for k = 1:nFrames
                idx = (k-1) * obj.HopLength + (1:obj.FrameLength);
                if idx(end) > numel(audio), break; end
                X = fft(audio(idx) .* win);
                S(:, k) = X(1:nBins);
            end
            freqs = (0:nBins-1)' * obj.SampleRate / obj.FrameLength;
            times = ((0:nFrames-1) * obj.HopLength + obj.FrameLength/2) / obj.SampleRate;
        end

        function avail = peripheralAvailability(obj, magDb, freqs)
            % normalize to peak, subtract a masking floor, apply the dominance
            % region weighting. output is in [0, 1].
            rel = magDb - max(magDb, [], "all");
            avail = (rel - obj.MaskingFloorDb) / (0 - obj.MaskingFloorDb);
            avail = max(0, min(1, avail));

            % critical-band smoothing along frequency. equivalent rectangular
            % bandwidth at center frequency f_c, glasberg and moore 1990:
            %   erb(f) = 24.7 * (1 + 4.37 * f / 1000)
            % approximate by smoothing each column with a variable gaussian.
            avail = obj.smoothAlongErb(avail, freqs, obj.MaskingSpreadErb);

            % dominance region weighting
            weight = ones(size(freqs));
            in = freqs >= obj.DominanceLowHz & freqs <= obj.DominanceHighHz;
            weight(in) = 1 + obj.DominanceWeight;
            weight = weight / max(weight);
            avail = avail .* weight;
        end

        function P = featurePresence(~, mag)
            % simple normalized magnitude. the raw "is there something here."
            P = mag / max(mag, [], "all");
        end

        function P = featurePersistence(obj, presence)
            % leaky integrator along time. tau in seconds.
            dt = obj.HopLength / obj.SampleRate;
            alpha = exp(-dt / obj.PersistenceTau);
            P = zeros(size(presence));
            prev = zeros(size(presence, 1), 1);
            for k = 1:size(presence, 2)
                prev = alpha * prev + (1 - alpha) * presence(:, k);
                P(:, k) = prev;
            end
            P = P / max(P, [], "all");
        end

        function C = featureContinuity(obj, presence, freqs)
            % how well does energy at (t, f) align with energy at (t-1, f)
            % and with nearby frequencies. product of short time-lag
            % correlation and local frequency smoothness.
            timeLag = [zeros(size(presence, 1), 1), presence(:, 1:end-1)];
            timeCoherent = sqrt(presence .* timeLag);

            freqSmoothed = obj.smoothAlongErb(presence, freqs, obj.ContinuityErbSigma);
            freqCoherent = 1 - abs(presence - freqSmoothed);

            C = timeCoherent .* max(0, freqCoherent);
            mx = max(C, [], "all");
            if mx > 0, C = C / mx; end
        end

        function D = featureChange(obj, presence)
            % rectified positive derivative of presence. short time constant.
            dt = obj.HopLength / obj.SampleRate;
            alpha = exp(-dt / obj.ChangeTau);
            smooth = zeros(size(presence));
            prev = zeros(size(presence, 1), 1);
            for k = 1:size(presence, 2)
                prev = alpha * prev + (1 - alpha) * presence(:, k);
                smooth(:, k) = prev;
            end
            D = max(0, presence - smooth);
            mx = max(D, [], "all");
            if mx > 0, D = D / mx; end
        end

        function H = featureHarmonicCoherence(~, mag, ~)
            % stub. returns ones so it does not dominate the product.
            % a future revision should correlate local structure against
            % comb templates or compute a time-frequency coherence score.
            H = ones(size(mag));
        end

        function Y = smoothAlongErb(~, X, freqs, sigmaErb)
            % smooth each time column along frequency with a width that grows
            % with frequency, approximating the equivalent rectangular bandwidth.
            Y = zeros(size(X));
            erb = 24.7 * (1 + 4.37 * freqs / 1000);
            for bin = 1:numel(freqs)
                sigmaHz = sigmaErb * erb(bin);
                % turn sigmaHz into a bin-space sigma
                binHz = freqs(2) - freqs(1);
                sigmaBins = max(1, sigmaHz / binHz);
                halfWin = ceil(3 * sigmaBins);
                lo = max(1, bin - halfWin);
                hi = min(numel(freqs), bin + halfWin);
                k = (lo:hi)';
                w = exp(-0.5 * ((k - bin) / sigmaBins) .^ 2);
                w = w / sum(w);
                Y(bin, :) = w' * X(k, :);
            end
        end

        function plotHeatmap(~, times, freqs, M, ttl, clim, freqLim)
            nexttile;
            imagesc(times, freqs, M, clim);
            axis xy;
            ylim(freqLim);
            xlabel("time, seconds");
            ylabel("frequency, hz");
            title(ttl);
            colormap(gca, "turbo");
            colorbar;
        end
    end
end
