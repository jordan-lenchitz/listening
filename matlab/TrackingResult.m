classdef TrackingResult < handle
    % TRACKINGRESULT Container for Multi-F0 tracking results with visualization
    %
    % Properties:
    %   Times        - Time axis (seconds)
    %   SungVoices   - Cell array of sung voice track structs
    %   ExtraPitches - Cell array of ghost/combination tone tracks
    %   SampleRate   - Sample rate used
    %   HopLength    - Hop length used
    %
    % Methods:
    %   visualize()   - Create plot of tracking results
    %   exportCSV()   - Export to CSV file
    %   summary()     - Print text summary
    %   getVoice(n)   - Get nth voice as timetable

    properties
        Times (1,:) double
        SungVoices (:,1) cell
        ExtraPitches (:,1) cell
        SampleRate (1,1) double
        HopLength (1,1) double
    end

    properties (Dependent)
        NumVoices
        NumGhosts
        Duration
    end

    methods
        function obj = TrackingResult(times, voices, ghosts, sr, hop)
            arguments
                times (1,:) double
                voices (:,1) cell
                ghosts (:,1) cell
                sr (1,1) double
                hop (1,1) double
            end
            obj.Times = times;
            obj.SungVoices = voices;
            obj.ExtraPitches = ghosts;
            obj.SampleRate = sr;
            obj.HopLength = hop;
        end

        function n = get.NumVoices(obj)
            n = numel(obj.SungVoices);
        end

        function n = get.NumGhosts(obj)
            n = numel(obj.ExtraPitches);
        end

        function d = get.Duration(obj)
            d = obj.Times(end);
        end

        function fig = visualize(obj, options)
            % VISUALIZE Create visualization of tracking results
            arguments
                obj
                options.OutputPath string = ""
                options.ShowGhosts logical = true
                options.YLim (1,2) double = [0, 0]
                options.Title string = "Multi-F0 Voice Tracking"
            end

            fig = figure(Position=[100, 100, 1400, 800], Color="white");
            hold on;

            colors = [ ...
                0.180, 0.525, 0.671;   % Blue
                0.635, 0.231, 0.447;   % Purple  
                0.945, 0.561, 0.004;   % Orange
                0.780, 0.243, 0.114;   % Red
                0.153, 0.682, 0.376;   % Green
                0.580, 0.404, 0.741];  % Violet

            legendH = []; legendT = string.empty;

            % Plot sung voices
            for i = 1:obj.NumVoices
                t = obj.SungVoices{i};
                c = colors(mod(i-1, height(colors))+1, :);
                tt = obj.Times(t.Frames);
                pp = t.Pitches;

                h = plot(tt, pp, "-", Color=c, LineWidth=2.5);
                legendH(end+1) = h;
                legendT(end+1) = sprintf("Voice %d (%.0f Hz)", i, mean(pp));

                % Entry marker (circle)
                plot(tt(1), pp(1), "o", Color=c, MarkerSize=14, MarkerFaceColor="white", LineWidth=2.5);
                % Exit marker (x)
                plot(tt(end), pp(end), "x", Color=c, MarkerSize=14, LineWidth=2.5);
            end

            % Plot ghost pitches
            if options.ShowGhosts && obj.NumGhosts > 0
                for i = 1:obj.NumGhosts
                    t = obj.ExtraPitches{i};
                    tt = obj.Times(t.Frames);
                    pp = t.Pitches;
                    h = plot(tt, pp, "--", Color=[0.5, 0, 0.5], LineWidth=2);
                    if i == 1
                        legendH(end+1) = h;
                        legendT(end+1) = "Ghost Pitch";
                    end
                end
            end

            xlabel("Time (seconds)", FontSize=14, FontWeight="bold");
            ylabel("Frequency (Hz)", FontSize=14, FontWeight="bold");
            title(options.Title, FontSize=16, FontWeight="bold");

            % Auto y-limits if not specified
            if all(options.YLim == 0)
                allPitches = cellfun(@(t) t.Pitches, obj.SungVoices, UniformOutput=false);
                allPitches = [allPitches{:}];
                if ~isempty(allPitches)
                    ylim([min(allPitches)*0.8, max(allPitches)*1.2]);
                end
            else
                ylim(options.YLim);
            end

            grid on;
            set(gca, GridAlpha=0.3, FontSize=12);
            legend(legendH, legendT, Location="northeast", FontSize=11);

            % Annotation
            annotation("textbox", [0.15, 0.01, 0.7, 0.04], ...
                String="○ = Voice Entry    ✕ = Voice Exit", ...
                EdgeColor="none", HorizontalAlignment="center", FontSize=11);

            hold off;

            if options.OutputPath ~= ""
                exportgraphics(fig, options.OutputPath, Resolution=300);
                fprintf("Figure saved to: %s\n", options.OutputPath);
            end
        end

        function exportCSV(obj, filepath)
            % EXPORTCSV Export tracking results to CSV
            arguments
                obj
                filepath string
            end

            allTracks = [obj.SungVoices; obj.ExtraPitches];
            
            % Pre-allocate
            nRows = sum(cellfun(@(t) numel(t.Frames), allTracks));
            data = table(Size=[nRows, 5], ...
                VariableTypes=["double","double","double","double","logical"], ...
                VariableNames=["time","voice_id","frequency_hz","confidence","is_extra"]);
            
            row = 1;
            for i = 1:numel(allTracks)
                t = allTracks{i};
                for j = 1:numel(t.Frames)
                    data.time(row) = obj.Times(t.Frames(j));
                    data.voice_id(row) = t.Id;
                    data.frequency_hz(row) = t.Pitches(j);
                    data.confidence(row) = t.Confidences(j);
                    data.is_extra(row) = t.IsExtra;
                    row = row + 1;
                end
            end

            writetable(data, filepath);
            fprintf("Exported to: %s\n", filepath);
        end

        function tt = getVoice(obj, n)
            % GETVOICE Get voice n as a timetable
            arguments
                obj
                n (1,1) double {mustBePositive, mustBeInteger}
            end

            if n > obj.NumVoices
                error("Only %d voices detected", obj.NumVoices);
            end

            t = obj.SungVoices{n};
            tt = timetable( ...
                seconds(obj.Times(t.Frames))', ...
                t.Pitches', t.Confidences', ...
                VariableNames=["Frequency_Hz", "Confidence"]);
        end

        function summary(obj)
            % SUMMARY Print summary of tracking results
            
            fprintf("\n%s\n", repmat("=", 1, 55));
            fprintf("  TRACKING SUMMARY\n");
            fprintf("%s\n\n", repmat("=", 1, 55));
            fprintf("  Duration: %.2f seconds\n", obj.Duration);
            fprintf("  Sung Voices: %d\n", obj.NumVoices);

            for i = 1:obj.NumVoices
                t = obj.SungVoices{i};
                entryT = obj.Times(t.Frames(1));
                exitT = obj.Times(t.Frames(end));
                meanF0 = mean(t.Pitches);

                % Voice part identification
                if meanF0 < 125
                    part = "Bass";
                elseif meanF0 < 155
                    part = "Baritone";
                elseif meanF0 < 185
                    part = "Lead";
                elseif meanF0 < 300
                    part = "Tenor";
                else
                    part = "Soprano";
                end

                fprintf("\n  Voice %d (%s):\n", i, part);
                fprintf("    Entry: %.2f s  |  Exit: %.2f s\n", entryT, exitT);
                fprintf("    Mean F0: %.1f Hz  |  Range: %.1f - %.1f Hz\n", ...
                    meanF0, min(t.Pitches), max(t.Pitches));
            end

            if obj.NumGhosts > 0
                fprintf("\n  Ghost Pitches: %d\n", obj.NumGhosts);
                for i = 1:min(3, obj.NumGhosts)
                    t = obj.ExtraPitches{i};
                    fprintf("    Ghost %d: ~%.1f Hz\n", i, mean(t.Pitches));
                end
                if obj.NumGhosts > 3
                    fprintf("    ... and %d more\n", obj.NumGhosts - 3);
                end
            end

            fprintf("\n%s\n", repmat("=", 1, 55));
        end
    end
end
