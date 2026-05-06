classdef justintonation
    % justintonation  helpers for building chords from integer ratios.
    %
    % everything is static!
    % no state :) :) :)
    % use as a namespace (please)
    %
    % common five-limit ratios fyi!
    %   unison      1:1
    %   minor third 6:5
    %   major third 5:4
    %   fourth      4:3
    %   fifth       3:2
    %   minor sixth 8:5
    %   major sixth 5:3
    %   minor seventh 9:5 (but try 7:4 for a much cooler harmonic seventh)
    %   octave      2:1
    %
    % barbershop dominant seventh in just intonation:
    %   [1 1; 5 4; 3 2; 7 4]   % root, major third, fifth, harmonic seventh
    %
    % sardinian tenores typical sonority, approximate:
    %   [1 1; 3 2; 2 1; 5 2]   % bassu, contra, bogi, mesu bogi
    %
    % usage:
    %   freqs = justintonation.chord(110, [1 1; 5 4; 3 2; 7 4]);
    %   cents = justintonation.centsFromEqualTempered(freqs);

    methods (Static)

        function freqs = chord(rootHz, ratios)
            % build chord frequencies from a root and an n-by-2 ratio matrix.
            arguments
                rootHz (1,1) double {mustBePositive}
                ratios (:,2) double {mustBePositive}
            end
            freqs = rootHz .* ratios(:,1) ./ ratios(:,2);
            freqs = freqs(:)';
        end

        function c = cents(f1, f2)
            % absolute cents distance between two frequencies.
            arguments
                f1 (1,1) double {mustBePositive}
                f2 (1,1) double {mustBePositive}
            end
            c = abs(1200 * log2(f1 / f2));
        end

        function c = centsFromEqualTempered(freqs, a4)
            % signed cents deviation from the nearest equal-tempered pitch.
            % positive means sharp, negative means flat.
            arguments
                freqs (1,:) double {mustBePositive}
                a4 (1,1) double = 440
            end
            semis = 12 * log2(freqs / a4);
            nearest = round(semis);
            c = 100 * (semis - nearest);
        end

        function name = nearestNoteName(freq, a4)
            % nearest twelve-tone note name with octave number.
            arguments
                freq (1,1) double {mustBePositive}
                a4 (1,1) double = 440
            end
            names = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
            semisFromA4 = round(12 * log2(freq / a4));
            % midi number: a4 is 69
            midi = 69 + semisFromA4;
            octave = floor(midi / 12) - 1;
            pc = mod(midi, 12) + 1;
            name = sprintf("%s%d", names(pc), octave);
        end

        function combos = combinationTones(freqs, orders)
            % generate expected combination tone frequencies for a set of sung pitches.
            %
            % includes:
            %   first-order difference tones:   abs(f2 - f1)
            %   cubic difference tones:         2*f1 - f2  and  2*f2 - f1
            %   second-order sums:              f1 + f2    (rare but listable)
            %
            % orders controls which families to include:
            %   "difference"  just f2 - f1
            %   "cubic"       cubic difference tones
            %   "all"         default, everything above
            arguments
                freqs (1,:) double {mustBePositive}
                orders (1,1) string = "all"
            end
            n = numel(freqs);
            combos = [];
            for i = 1:n
                for j = i+1:n
                    f1 = freqs(i); f2 = freqs(j);
                    if f2 < f1, tmp = f1; f1 = f2; f2 = tmp; end
                    if orders == "difference" || orders == "all"
                        combos(end+1) = f2 - f1; %#ok<*AGROW>
                    end
                    if orders == "cubic" || orders == "all"
                        combos(end+1) = 2*f1 - f2;
                        combos(end+1) = 2*f2 - f1;
                    end
                end
            end
            combos = combos(combos > 0);
        end

        function overtones = harmonicSeries(f0, n)
            % first n harmonics of f0. includes the fundamental.
            arguments
                f0 (1,1) double {mustBePositive}
                n (1,1) double {mustBePositive, mustBeInteger} = 8
            end
            overtones = f0 * (1:n);
        end

        function printChord(freqs)
            % pretty-print a chord with note names and cents deviation.
            arguments
                freqs (1,:) double {mustBePositive}
            end
            fprintf("%-8s %-8s %s\n", "freq", "note", "cents from equal-tempered");
            fprintf("%s\n", repmat('-', 1, 45));
            dev = justintonation.centsFromEqualTempered(freqs);
            for i = 1:numel(freqs)
                note = justintonation.nearestNoteName(freqs(i));
                fprintf("%-8.2f %-8s %+6.1f\n", freqs(i), note, dev(i));
            end
        end

    end
end
