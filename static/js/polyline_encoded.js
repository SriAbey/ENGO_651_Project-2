/**
 * Polyline encoding/decoding utility
 * Based on Google's polyline algorithm with Leaflet integration
 */
(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        // AMD
        define(['leaflet'], factory);
    } else if (typeof module === 'object' && module.exports) {
        // Node/CommonJS
        module.exports = factory(require('leaflet'));
    } else {
        // Browser globals
        if (typeof L === 'undefined') {
            throw new Error('Leaflet must be loaded first');
        }
        factory(L);
    }
}(this, function (L) {
    'use strict';

    const PolylineUtil = {
        /**
         * Default encoding options
         * @param {Object|Number} options - Options object or precision number
         * @returns {Object} Normalized options
         */
        defaultOptions: function (options) {
            if (typeof options === 'number') {
                options = { precision: options };
            } else {
                options = options || {};
            }

            return {
                precision: options.precision || 5,
                factor: options.factor || Math.pow(10, options.precision || 5),
                dimension: options.dimension || 2
            };
        },

        /**
         * Encode an array of points
         * @param {Array} points - Array of LatLng objects or [lat,lng] arrays
         * @param {Object} options - Encoding options
         * @returns {String} Encoded polyline string
         */
        encode: function (points, options) {
            if (!points || !points.length) {
                return '';
            }

            options = this.defaultOptions(options);
            const flatPoints = this._flattenPoints(points, options.dimension);
            return this.encodeDeltas(flatPoints, options);
        },

        /**
         * Decode an encoded string to an array of points
         * @param {String} encoded - Encoded polyline string
         * @param {Object} options - Decoding options
         * @returns {Array} Array of [lat,lng] arrays
         */
        decode: function (encoded, options) {
            if (!encoded) {
                return [];
            }

            options = this.defaultOptions(options);
            const flatPoints = this.decodeDeltas(encoded, options);
            return this._unflattenPoints(flatPoints, options.dimension);
        },

        // Internal helper methods
        _flattenPoints: function (points, dimension) {
            const flatPoints = [];
            
            for (let i = 0, len = points.length; i < len; i++) {
                const point = points[i];
                
                if (dimension === 2) {
                    flatPoints.push(point.lat != null ? point.lat : point[0]);
                    flatPoints.push(point.lng != null ? point.lng : point[1]);
                } else {
                    for (let dim = 0; dim < dimension; dim++) {
                        flatPoints.push(point[dim]);
                    }
                }
            }
            
            return flatPoints;
        },

        _unflattenPoints: function (flatPoints, dimension) {
            const points = [];
            
            for (let i = 0, len = flatPoints.length; i + (dimension - 1) < len;) {
                const point = [];
                
                for (let dim = 0; dim < dimension; dim++) {
                    point.push(flatPoints[i++]);
                }
                
                points.push(point);
            }
            
            return points;
        },

        // Core encoding/decoding methods
        encodeDeltas: function (numbers, options) {
            options = this.defaultOptions(options);
            const lastNumbers = new Array(options.dimension).fill(0);
            
            for (let i = 0, len = numbers.length; i < len;) {
                for (let d = 0; d < options.dimension; d++, i++) {
                    const num = parseFloat(numbers[i]).toFixed(options.precision);
                    const delta = num - (lastNumbers[d] || 0);
                    lastNumbers[d] = num;
                    numbers[i] = delta;
                }
            }
            
            return this.encodeFloats(numbers, options);
        },

        decodeDeltas: function (encoded, options) {
            options = this.defaultOptions(options);
            const numbers = this.decodeFloats(encoded, options);
            const lastNumbers = new Array(options.dimension).fill(0);
            
            for (let i = 0, len = numbers.length; i < len;) {
                for (let d = 0; d < options.dimension; d++, i++) {
                    numbers[i] = Math.round(
                        (lastNumbers[d] = numbers[i] + (lastNumbers[d] || 0)) * 
                        options.factor
                    ) / options.factor;
                }
            }
            
            return numbers;
        },

        encodeFloats: function (numbers, options) {
            options = this.defaultOptions(options);
            
            for (let i = 0, len = numbers.length; i < len; i++) {
                numbers[i] = Math.round(numbers[i] * options.factor);
            }
            
            return this.encodeSignedIntegers(numbers);
        },

        decodeFloats: function (encoded, options) {
            options = this.defaultOptions(options);
            const numbers = this.decodeSignedIntegers(encoded);
            
            for (let i = 0, len = numbers.length; i < len; i++) {
                numbers[i] /= options.factor;
            }
            
            return numbers;
        },

        encodeSignedIntegers: function (numbers) {
            for (let i = 0, len = numbers.length; i < len; i++) {
                const num = numbers[i];
                numbers[i] = (num < 0) ? ~(num << 1) : (num << 1);
            }
            
            return this.encodeUnsignedIntegers(numbers);
        },

        decodeSignedIntegers: function (encoded) {
            const numbers = this.decodeUnsignedIntegers(encoded);
            
            for (let i = 0, len = numbers.length; i < len; i++) {
                const num = numbers[i];
                numbers[i] = (num & 1) ? ~(num >> 1) : (num >> 1);
            }
            
            return numbers;
        },

        encodeUnsignedIntegers: function (numbers) {
            let encoded = '';
            
            for (let i = 0, len = numbers.length; i < len; i++) {
                encoded += this.encodeUnsignedInteger(numbers[i]);
            }
            
            return encoded;
        },

        decodeUnsignedIntegers: function (encoded) {
            const numbers = [];
            let current = 0;
            let shift = 0;
            
            for (let i = 0, len = encoded.length; i < len; i++) {
                const b = encoded.charCodeAt(i) - 63;
                current |= (b & 0x1f) << shift;
                
                if (b < 0x20) {
                    numbers.push(current);
                    current = 0;
                    shift = 0;
                } else {
                    shift += 5;
                }
            }
            
            return numbers;
        },

        encodeUnsignedInteger: function (num) {
            let value;
            let encoded = '';
            
            while (num >= 0x20) {
                value = (0x20 | (num & 0x1f)) + 63;
                encoded += String.fromCharCode(value);
                num >>= 5;
            }
            
            value = num + 63;
            encoded += String.fromCharCode(value);
            
            return encoded;
        }
    };

    // Leaflet integration
    if (typeof L !== 'undefined') {
        L.PolylineUtil = PolylineUtil;
        
        if (!L.Polyline.fromEncoded) {
            L.Polyline.fromEncoded = function (encoded, options) {
                return new L.Polyline(PolylineUtil.decode(encoded), options);
            };
        }
        
        if (!L.Polygon.fromEncoded) {
            L.Polygon.fromEncoded = function (encoded, options) {
                return new L.Polygon(PolylineUtil.decode(encoded), options);
            };
        }
        
        const encodeMixin = {
            encodePath: function () {
                return PolylineUtil.encode(this.getLatLngs());
            }
        };
        
        L.Polyline.include(encodeMixin);
        L.Polygon.include(encodeMixin);
    }

    return PolylineUtil;
}));