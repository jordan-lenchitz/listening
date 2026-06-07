DualProcessTracker {
    var <fmin, <fmax, <gridBinsPerOct;
    var <freqGrid, <transitionMatrix;
    var <>sigmaCents, <>alphaBase, <>fadeFactor, <>voicingThresh, <>harmCombWidth;
    var <gaborBankWindow, <gaborBank;

    *new { |fmin = 80.0, fmax = 4000.0, binsPerOct = 60|
        ^super.new.init(fmin, fmax, binsPerOct);
    }

    init { |argFmin, argFmax, argBinsPerOct|
        fmin = argFmin;
        fmax = argFmax;
        gridBinsPerOct = argBinsPerOct;
        
        sigmaCents = 25.0;
        alphaBase = 0.6;
        fadeFactor = 0.98;
        voicingThresh = 0.2;
        harmCombWidth = 4;

        this.calcFreqGrid;
        this.buildTransitionMatrix;
    }

    calcFreqGrid {
        var nOct = (fmax / fmin).log2;
        var nBins = (nOct * gridBinsPerOct).ceil.asInteger;
        freqGrid = FloatArray.fill(nBins, { |i|
            fmin * (2.0 ** (i / gridBinsPerOct))
        });
    }

    buildTransitionMatrix {
        var n = freqGrid.size;
        var lg = freqGrid.collect(_.log);
        transitionMatrix = Array.fill(n, { FloatArray.newClear(n) });

        n.do { |j|
            var sigmaLn = (sigmaCents / 1200.0) / (freqGrid[j] / 1000.0);
            var sum = 0.0;
            var col = FloatArray.newClear(n);
            n.do { |i|
                var val = ( (-( (lg[i] - lg[j]).squared )) / (2.0 * (sigmaLn.squared)) ).exp;
                col[i] = val;
                sum = sum + val;
            };
            if (sum > 0) {
                n.do { |i| transitionMatrix[i].put(j, col[i] / sum) };
            } {
                transitionMatrix[j].put(j, 1.0);
            };
        };
    }

    harmonicCombWeight { |p|
        var n = p.size;
        var combP = p.copy;
        (2..harmCombWidth).do { |m|
            var shift = (n / m).round.asInteger;
            if (shift < n) {
                (0..n - shift - 1).do { |i|
                    combP[i] = combP[i] + (p[i + shift] / (m.asFloat.squared));
                };
            };
        };
        ^combP;
    }

    fastPrior { |f0|
        var n = freqGrid.size;
        var fp = FloatArray.newClear(n);
        var lg, mu, sigmaLn, sum;
        
        if (f0.isNil || { f0 <= 0 }) {
            ^FloatArray.fill(n, 1.0 / n);
        };

        lg = freqGrid.collect(_.log);
        mu = f0.log;
        sigmaLn = 15.0 / 1200.0;
        sum = 0.0;
        
        n.do { |i|
            var val = (-(lg[i] - mu).squared / (2 * sigmaLn.squared)).exp;
            fp[i] = val;
            sum = sum + val;
        };
        
        if (sum > 0) { ^fp / sum } { ^FloatArray.fill(n, 1.0 / n) };
    }

    // In SC, we'd typically use UGens for the actual processing.
    // This Class structure captures the architectural "Dual Process" intent.
}