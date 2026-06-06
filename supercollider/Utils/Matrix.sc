Matrix {
    var <rows, <cols, <data;

    *new { |rows, cols|
        ^super.new.init(rows, cols);
    }

    *fromArray { |rows, cols, array|
        var m = Matrix.new(rows, cols);
        m.setData(array);
        ^m;
    }
    
    *identity { |size|
        var m = Matrix.new(size, size);
        var d = FloatArray.fill(size * size, 0);
        size.do { |i| d[i * size + i] = 1.0 };
        m.setData(d);
        ^m;
    }

    init { |r, c|
        rows = r;
        cols = c;
        data = FloatArray.fill(rows * cols, 0);
    }

    setData { |d|
        if(d.size != (rows * cols)) {
            "Matrix: Data size mismatch".error;
            ^this;
        };
        data = d.as(FloatArray);
    }

    at { |r, c|
        ^data[r * cols + c];
    }

    put { |r, c, val|
        data[r * cols + c] = val;
    }

    + { |other|
        if(other.isKindOf(Matrix)) {
            if(rows != other.rows or: { cols != other.cols }) { "Dimension mismatch".error; ^nil };
            ^Matrix.fromArray(rows, cols, data + other.data);
        };
        ^Matrix.fromArray(rows, cols, data + other);
    }

    - { |other|
        if(other.isKindOf(Matrix)) {
            if(rows != other.rows or: { cols != other.cols }) { "Dimension mismatch".error; ^nil };
            ^Matrix.fromArray(rows, cols, data - other.data);
        };
        ^Matrix.fromArray(rows, cols, data - other);
    }

    * { |other|
        if(other.isNumber) {
            ^Matrix.fromArray(rows, cols, data * other);
        };
        if(other.isKindOf(Matrix)) {
            var res, r, c, k, sum;
            if(cols != other.rows) { "Inner dimension mismatch".error; ^nil };
            res = Matrix.new(rows, other.cols);
            rows.do { |r|
                other.cols.do { |c|
                    sum = 0;
                    cols.do { |k|
                        sum = sum + (this.at(r, k) * other.at(k, c));
                    };
                    res.put(r, c, sum);
                };
            };
            ^res;
        };
        "Unsupported multiplication".error;
        ^nil;
    }

    transpose {
        var res = Matrix.new(cols, rows);
        rows.do { |r|
            cols.do { |c|
                res.put(c, r, this.at(r, c));
            };
        };
        ^res;
    }

    // Mocked inverse for the "POC"
    inverse {
        if(rows != cols) { "Only square matrices can be inverted".error; ^nil };
        // In a real implementation, we'd use Gaussian elimination or LU decomposition
        postln("Matrix: Warning - Using mocked identity inverse for POC.");
        ^Matrix.identity(rows);
    }

    print {
        postln("Matrix (" + rows + "x" + cols + "):");
        rows.do { |r|
            var rowStr = "  [ ";
            cols.do { |c|
                rowStr = rowStr + this.at(r, c).asString.padLeft(8) + " ";
            };
            postln(rowStr + "]");
        };
    }
}
