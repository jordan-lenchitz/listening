classdef DualProcessPitchTracker
    % requires Wavelet Toolbox for wsst / wsstridge
    % ===================== public properties =====================
    properties
        AudioFile           string  = "audio.wav"
        FrameDuration       double  = 0.03
        FrameShift          double  = 0.01
        Fmin                double  = 80
        Fmax                double  = 4000
        GridBinsPerOct      double  = 60
        AlphaBase           double  = 0.6
        FadeFactor          double  = 0.98
        VoicingThresh       double  = 0.2
        SigmaCents          double  = 25
        HarmCombWidth       double  = 4
        TrackAssocCents     double  = 35
        KLAlertThresh       double  = 0.5
        UseGPU             logical  = false
        UseParfor          logical  = false

        % -------------- synchrosqueeze options ----------------
        UseSynSQ           logical  = true      % master toggle
        BetaSynSQ          double   = 0.3       % ridge-prior weight
        SsqVoicesPerOctave double   = 48        % CWT density
    end

    % ================ read-only result properties ================
    properties (SetAccess = private)
        Tracks
        Fs              double
        TimeAxis        double
        FastF0          double
        FastConf        double
        Posteriors      double     
        KLdiv           double

        % ----------- synchrosqueeze result bundle -------------
        SynSQ struct = struct( 
            'Time',      [], 
            'Freq',      [], % matrix of ridge frequencies, rows = ridges
            'TFR',       [], 
            'FreqAxis',  [] )
    end

    % ================= PRIVATE (internal state) ==================
    properties (Access = private)
        audio           double
        frameLen
        frameStep
        freqGrid
        gaborBank
        transitionMat
    end

    % =========================  api  ==============================
    methods
        % -------- Constructor -------------------------------------
        function obj = DualProcessPitchTracker(varargin)
            obj = obj.parseInputs(varargin{:});
            [obj.audio, obj.Fs] = audioread(obj.AudioFile);
            if size(obj.audio, 2) > 1
                obj.audio = mean(obj.audio, 2);
            end

            obj.frameLen  = round(obj.FrameDuration * obj.Fs);
            obj.frameStep = round(obj.FrameShift   * obj.Fs);
            nF = floor((length(obj.audio) - obj.frameLen) / obj.frameStep) + 1;
            obj.TimeAxis  = ((0:nF - 1) * obj.FrameShift) + obj.FrameDuration / 2;

            obj.calcFreqGrid();
            obj.buildGaborBank();
            obj.buildTransitionMatrix();
            if obj.UseSynSQ
                obj.computeSynchrosqueeze();
            end
        end

        % ----------------- main pipeline --------------------------
        function run(obj)
            nF = numel(obj.TimeAxis);
            nG = numel(obj.freqGrid);

            obj.FastF0     = nan(nF, 1);
            obj.FastConf   = zeros(nF, 1);
            obj.Posteriors = zeros(nG, nF);
            obj.KLdiv      = zeros(nF, 1);

            % ===== YIN pass ==============================
            for i = 1:nF
                idx   = (i - 1) * obj.frameStep + (1:obj.frameLen);
                frame = obj.audio(idx) - mean(obj.audio(idx));
                [f0, ~, conf] = pitch(frame, obj.Fs, 
                                      'Method',        'YIN', 
                                      'Range',         [obj.Fmin obj.Fmax], 
                                      'WindowLength',  obj.frameLen, 
                                      'OverlapLength', 0);
                obj.FastF0(i)   = f0;
                obj.FastConf(i) = conf;
            end

            % ===== Bayesian filtering ====================
            Prior = ones(nG, 1) / nG;
            fade = obj.FadeFactor;
            rfI = nan(nF, 1);
            if obj.UseSynSQ
                % interpolate ridge (take 1st ridge) to frame centres
                rfI = interp1(obj.SynSQ.Time,obj.SynSQ.Freq(1,:),obj.TimeAxis,'linear','extrap');
            end

            for i = 1:nF
                idx       = (i - 1) * obj.frameStep + (1:obj.frameLen);
                frame_raw = obj.audio(idx) - mean(obj.audio(idx));

                % ----- early exit for unvoiced ----------------------
                if obj.FastConf(i) < obj.VoicingThresh
                    obj.Posteriors(:, i) = prior;
                    obj.KLdiv(i)         = 0;
                    prior = fade * prior + (1 - fade) * (ones(nG, 1) / nG);
                    continue
                end

                % ----- measurement likelihood (vectorised Gabor) ----
                frame_win = (frame_raw .* obj.gaborBank.window).';
                coeff     = obj.gaborBank.bank * frame_win;
                P         = abs(coeff).^2;
                P         = obj.harmonicCombWeight(P);
                measLh    = P / sum(P);

                % ----- fast prior -------------------------
                fp = obj.fastPrior(obj.FastF0(i));

                % ----- synchrosqueeze ridge prior -------------------
                if obj.UseSynSQ
                    rp = obj.fastPrior(ridgeF_interp(i));
                else
                    rp = zeros(size(fp));
                end

                % attention weights
                alpha_i = obj.AlphaBase * obj.FastConf(i);
                beta_i  = obj.BetaSynSQ;

                combPrior = (alpha_i) * fp + beta_i * rp + (1 - alpha_i - beta_i) * prior;
                combPrior = combPrior / sum(combPrior);

                % ----- Bayesian update ------------------------------
                predPrior            = obj.transitionMat * combPrior;
                post                 = predPrior .* measLh;
                post                 = post / sum(post);
                obj.Posteriors(:, i) = post;

                % ----- KL monitor -----------------------------------
                obj.KLdiv(i) = sum(post .* log(max(post, eps) ./ max(combPrior, eps)));
                if obj.KLdiv(i) > obj.KLAlertThresh
                    fprintf('[%.2fs] KL=%.2f -> override\n', obj.TimeAxis(i), obj.KLdiv(i));
                end

                % ----- fade memory ----------------------------------
                prior = fade * post + (1 - fade) * (ones(nG, 1) / nG);
            end

            % ===== multi-hypothesis tracking =======================
            obj.trackingHungarian();
        end

        % ---------------- plotting helpers ------------------------
        function plotTracks(obj)
            figure;
            hold on;
            % spectrogram underlay
            spectrogram(obj.audio,round(0.04*obj.Fs),[],[],obj.Fs,'yaxis','MinThreshold',-110);
            colormap parula;
            ylim([obj.Fmin obj.Fmax]);
            title('Dual-Process Pitch Tracking');
            xlabel('Time (s)');
            ylabel('Frequency (Hz)');

            % draw tracks
            colors = lines(numel(obj.Tracks));
            for k = 1:numel(obj.Tracks)
                tr = obj.Tracks(k);
                plot(tr.time, tr.f0, '-', 'LineWidth', 2, 'Color', colors(k, :));
            end
            hold off;
        end 	  

        function plotSynchrosqueeze(obj)
            if ~obj.UseSynSQ
                warning('Synchrosqueeze layer disabled.');
                return
            end
            figure;
            imagesc(obj.SynSQ.Time,obj.SynSQ.FreqAxis, 20 * log10(abs(obj.SynSQ.TFR)));
            axis xy;
            colormap turbo;
            colorbar;
            ylim([obj.Fmin obj.Fmax]);
            xlabel('Time (s)');
            ylabel('Frequency (Hz)');
            title('Synchrosqueezed Scalogram');
            hold on;
            plot(obj.SynSQ.Time, obj.SynSQ.Freq(1, :), 'w', 'LineWidth', 2);
            hold off;
        end
    end

    % ==================== internal helpers ========================
    methods (Access = private)

        % --------- generic name-value parser ----------------------
        function obj = parseInputs(obj, varargin)
            p = inputParser;                          %#ok<*MCN>
            p.KeepUnmatched = true;

            metaP = meta.class.fromName(class(obj));
            for pr = [metaP.PropertyList]
                if pr.SetAccess == "public"
                    addParameter(p, pr.Name, obj.(pr.Name));
                end
            end

            parse(p, varargin{:});
            flds = fieldnames(p.Results);
            for k = 1:numel(flds)
                obj.(flds{k}) = p.Results.(flds{k});
            end
        end

        % --------- logarithmically spaced frequency grid ---------
        function calcFreqGrid(obj)
            nOct  = log2(obj.Fmax / obj.Fmin);
            nBins = ceil(nOct * obj.GridBinsPerOct);
            obj.freqGrid = obj.Fmin * 2.^((0:nBins - 1) / obj.GridBinsPerOct).';
        end

        % --------- pre-compute Gabor bank & window ---------------
        function buildGaborBank(obj)
            t_axis = (-(obj.frameLen - 1) / 2 : (obj.frameLen - 1) / 2) / obj.Fs;
            sigma  = obj.FrameDuration / 6;
            gauss  = exp(-t_axis .^ 2 / (2 * sigma ^ 2));

            bank = exp(1i * 2 * pi * (obj.freqGrid * t_axis)) .* gauss;
            obj.gaborBank.window = gauss;
            obj.gaborBank.bank   = bank;
            if obj.UseGPU
                obj.gaborBank.bank = gpuArray(bank);
            end
        end

        % --------- adaptive Gaussian transition matrix ----------
        function buildTransitionMatrix(obj)
            lg = log(obj.freqGrid);
            % variance shrinks in absolute Hz for higher pitches
            sigma_ln = (obj.SigmaCents / 1200) ./ (obj.freqGrid / 1000);
            [X, Y] = ndgrid(lg, lg);
            T = exp(-(X - Y) .^ 2 ./ (2 * sigma_ln .^ 2));
            T = T ./ sum(T, 1);          % column-stochastic
            obj.transitionMat = T;
        end

        % --------- harmonic-comb weighting ----------------------
        function P = harmonicCombWeight(obj, P)
            combP = P;
            for m = 2 : obj.HarmCombWidth
                shift = round(numel(P) / m);
                combP(1 : end - shift) = combP(1 : end - shift) + P(1 + shift : end) / m ^ 2;
            end
            P = combP;
        end

        % --------- narrow Gaussian prior around f0 --------------
        function fp = fastPrior(obj, f0)
            if isnan(f0)
                fp = ones(numel(obj.freqGrid), 1) / numel(obj.freqGrid);
                return
            end
            lg         = log(obj.freqGrid);
            mu         = log(f0);
            sigma_ln   = 15 / 1200;      % 15 cents on ln-Hz scale
            fp         = exp(-(lg - mu) .^ 2 / (2 * sigma_ln ^ 2));
            fp         = fp / sum(fp);
        end

        % --------- multi-trajectory assignment ------
        function trackingHungarian(obj)
            nF     = size(obj.Posteriors, 2);
            peaks  = cell(nF, 1);
            topN   = 5;

            % peak picking per frame
            for i = 1 : nF
                [pk, loc] = findpeaks(obj.Posteriors(:, i), 'SortStr', 'descend');
                keep      = min(topN, numel(pk));
                peaks{i}  = [loc(1 : keep), pk(1 : keep)];
            end

            tracks = struct('time', {}, 'f0', {}, 'prob', {});
            if isempty(peaks{1})
                obj.Tracks = tracks;
                return
            end

            % initialise with first frame
            for j = 1 : size(peaks{1}, 1)
                tracks(j).time = obj.TimeAxis(1);
                tracks(j).f0   = obj.freqGrid(peaks{1}(j, 1));
                tracks(j).prob = peaks{1}(j, 2);
            end

            centsTol = obj.TrackAssocCents;

            % propagate through frames
            for i = 2 : nF
                candIdx = peaks{i}(:, 1);
                candF0  = obj.freqGrid(candIdx);
                nT      = numel(tracks);
                nC      = numel(candF0);

                % cost matrix in cents
                cost = centsTol * ones(nT, nC);
                for r = 1 : nT
                    lastF0 = tracks(r).f0(end);
                    if ~isnan(lastF0)
                        cost(r, :) = abs(1200 * log2(candF0 / lastF0));
                    end
                end

                [pairs, ~, unassC] = matchpairs(cost, centsTol);

                assigned = false(nC, 1);
                for p = 1 : size(pairs, 1)
                    r = pairs(p, 1);
                    c = pairs(p, 2);
                    tracks(r).time(end + 1) = obj.TimeAxis(i);
                    tracks(r).f0(end + 1)   = candF0(c);
                    tracks(r).prob(end + 1) = peaks{i}(c, 2);
                    assigned(c)             = true;
                end

                % new tracks for unassigned candidates
                for c = find(~assigned).'
                    tr.time = obj.TimeAxis(i);
                    tr.f0   = candF0(c);
                    tr.prob = peaks{i}(c, 2);
                    tracks(end + 1) = tr; %#ok<AGROW>
                end

                % gap placeholders for unpaired tracks
                for r = setdiff(1 : nT, pairs(:, 1).')
                    tracks(r).time(end + 1) = obj.TimeAxis(i);
                    tracks(r).f0(end + 1)   = NaN;
                    tracks(r).prob(end + 1) = 0;
                end
            end

            obj.Tracks = tracks;
        end
    end

        % -------- synchrosqueezed Morlet layer ----------------
        function computeSynchrosqueeze(obj)
            fprintf('Computing WSST (Morlet, %d voices/oct) ...\n', obj.SsqVoicesPerOctave);
            [tfr, f, t] = wsst(obj.audio, obj.Fs, ...
                               'VoicesPerOctave', obj.SsqVoicesPerOctave);
            % extract up to 3 ridges
            [~, iridge] = wsstridge(tfr, 'NumRidges', 3, ...
                                    'Penalty', 5, 'Window', 7);
            ridgeF = f(iridge);

            obj.SynSQ.Time      = t;
            obj.SynSQ.FreqAxis  = f;
            obj.SynSQ.TFR       = tfr;
            obj.SynSQ.Freq      = ridgeF;   % rows = ridges
            fprintf('WSST done – ridge 1 median f0 = %.1f Hz\n', median(ridgeF(1, :), 'omitnan'));
        end
    end
end

% ---------------- how to run in MATLAB -----------------------------
% tracker = DualProcessPitchTracker( 
%     'AudioFile',          'voice.wav', 
%     'UseSynSQ',           true, 
%     'BetaSynSQ',          0.25, 
%     'SsqVoicesPerOctave', 60 );
% tracker.run();
% tracker.plotSynchrosqueeze();
% tracker.plotTracks();
