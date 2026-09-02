/* Delivery-location picker.
 *
 * Renders into any element produced by the location_picker() macro
 * (templates/partials/location_picker.html) and keeps three hidden inputs -
 * latitude, longitude, map_link - in step with whatever the user does. The
 * form around it submits those exactly as it submits any other field; nothing
 * here posts anything by itself.
 *
 * Three ways in, because people arrive with the location in different forms:
 *   1. drag the pin (or tap the map)  -> coordinates, no link
 *   2. paste a Google Maps link       -> link, and usually coordinates too
 *   3. "Use my current location"      -> coordinates from the browser
 * Any one of them is enough. See maps.py for why the two halves are stored
 * separately instead of one being derived from the other.
 *
 * Leaflet + OpenStreetMap tiles rather than the Google Maps JavaScript API:
 * that API needs a billing-enabled key, and a picker that shows nothing until
 * someone sets up a Google Cloud project is a picker nobody uses. The location
 * is still handed back to Google - google_maps_url() in maps.py turns the
 * coordinates into a maps.google.com link, which is what staff actually open.
 *
 * Leaflet itself is lazy-loaded on first use, exactly like jsPDF and qrcode.js
 * in main.js: a visitor who never opens a page with a picker on it never pays
 * for it.
 */
(function () {
    'use strict';

    var LEAFLET_CSS = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css';
    var LEAFLET_JS = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js';

    // Phnom Penh. Only ever used as the *view* a picker with no pin opens on -
    // it is never written into the inputs, so an untouched picker still submits
    // empty coordinates rather than silently claiming the shop's own location.
    var DEFAULT_VIEW = [11.5564, 104.9282];
    var DEFAULT_ZOOM = 12;
    var PIN_ZOOM = 17;
    // One step wider than the picker's: a thumbnail wants a street or two of
    // context around the pin, not the rooftop.
    var PREVIEW_ZOOM = 16;

    var leafletPromise = null;

    function loadLeaflet() {
        if (window.L && window.L.map) return Promise.resolve(window.L);
        if (leafletPromise) return leafletPromise;

        leafletPromise = new Promise(function (resolve, reject) {
            if (!document.querySelector('link[data-leaflet]')) {
                var link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = LEAFLET_CSS;
                link.setAttribute('data-leaflet', '1');
                document.head.appendChild(link);
            }
            var script = document.createElement('script');
            script.src = LEAFLET_JS;
            script.onload = function () { resolve(window.L); };
            script.onerror = function () { reject(new Error('Failed to load Leaflet')); };
            document.head.appendChild(script);
        }).catch(function (err) {
            leafletPromise = null;
            throw err;
        });
        return leafletPromise;
    }

    // ---- link parsing (mirrors parse_coordinates() in maps.py) -------------
    // Duplicated in the browser on purpose: nearly every pasted link carries its
    // coordinates in plain sight, and parsing them here means the pin moves the
    // instant it is pasted instead of after a round trip. Only the short links
    // this cannot read (maps.app.goo.gl) go to the server - see resolveLink().
    var NUM = '-?\\d+(?:\\.\\d+)?';
    var PATTERNS = [
        new RegExp('!3d(' + NUM + ')!4d(' + NUM + ')'),
        new RegExp('[?&](?:q|query|ll|daddr|sll|center)=(?:loc:)?(' + NUM + ')%2C(' + NUM + ')', 'i'),
        new RegExp('[?&](?:q|query|ll|daddr|sll|center)=(?:loc:)?(' + NUM + ')\\s*,\\s*(' + NUM + ')', 'i'),
        new RegExp('@(' + NUM + '),(' + NUM + ')'),
        new RegExp('#map=\\d+(?:\\.\\d+)?/(' + NUM + ')/(' + NUM + ')')
    ];
    var BARE_PAIR = new RegExp('^\\s*(' + NUM + ')\\s*,\\s*(' + NUM + ')\\s*$');

    function toPair(latText, lngText) {
        var lat = parseFloat(latText);
        var lng = parseFloat(lngText);
        if (!isFinite(lat) || !isFinite(lng)) return null;
        if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
        if (lat === 0 && lng === 0) return null;   // see the same note in maps.py
        return { lat: lat, lng: lng };
    }

    function parseCoordinates(text) {
        text = (text || '').trim();
        if (!text) return null;

        var bare = BARE_PAIR.exec(text);
        if (bare) return toPair(bare[1], bare[2]);

        var candidates = [text];
        try { candidates.push(decodeURIComponent(text)); } catch (e) { /* malformed % escape */ }

        for (var c = 0; c < candidates.length; c++) {
            for (var p = 0; p < PATTERNS.length; p++) {
                var match = PATTERNS[p].exec(candidates[c]);
                if (match) {
                    var pair = toPair(match[1], match[2]);
                    if (pair) return pair;
                }
            }
        }
        return null;
    }

    function isShortLink(text) {
        return /^https?:\/\/(maps\.app\.goo\.gl|goo\.gl)\//i.test((text || '').trim());
    }

    // Mirrors _MAP_LINK_HOST_RE in store-api's schemas.py, which is what actually
    // enforces this - the copy here exists so a wrong paste is answered instantly
    // and never gets saved, instead of surfacing as a 422 after the whole profile
    // form is submitted. Keep the two in step.
    var MAP_HOST_RE = /^(?:[a-z0-9-]+\.)*(?:google\.[a-z.]{2,7}|goo\.gl|openstreetmap\.org|osm\.org)$/;

    function isMapHost(text) {
        try {
            var url = new URL(text);
            if (url.protocol !== 'http:' && url.protocol !== 'https:') return false;
            return MAP_HOST_RE.test(url.hostname.toLowerCase());
        } catch (e) {
            return false;   // not a URL at all
        }
    }

    // ---- pieces shared by the editable picker and the read-only preview ----
    var TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    var ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

    function tileLayer(L) {
        return L.tileLayer(TILE_URL, { maxZoom: 19, attribution: ATTRIBUTION });
    }

    /* A divIcon rather than Leaflet's default PNG: the default's image path is
     * resolved from the stylesheet's own URL, which is fragile behind a CDN, and
     * this one inherits the site's accent colour instead of shipping a blue that
     * belongs to no brand. */
    function pinIcon(L) {
        return L.divIcon({
            className: 'loc-pin',
            html: '<span class="loc-pin-dot"></span>',
            iconSize: [26, 26],
            iconAnchor: [13, 26]
        });
    }

    // ---- one picker instance ----------------------------------------------
    function Picker(root) {
        this.root = root;
        this.latInput = root.querySelector('[data-loc="latitude"]');
        this.lngInput = root.querySelector('[data-loc="longitude"]');
        this.linkInput = root.querySelector('[data-loc="map_link"]');
        this.urlField = root.querySelector('[data-loc="url-field"]');
        this.mapEl = root.querySelector('[data-loc="map"]');
        this.statusEl = root.querySelector('[data-loc="status"]');
        this.openEl = root.querySelector('[data-loc="open"]');
        this.map = null;
        this.marker = null;
        this.bind();
        this.syncStatus();
    }

    Picker.prototype.bind = function () {
        var self = this;

        this.root.querySelector('[data-loc="locate"]').addEventListener('click', function () {
            self.useBrowserLocation();
        });
        this.root.querySelector('[data-loc="clear"]').addEventListener('click', function () {
            self.clear();
        });

        // Paste, typing and blur all funnel to the same place. `paste` fires
        // BEFORE the value lands in the field, hence the deferral - reading it
        // synchronously gets the previous value.
        this.urlField.addEventListener('paste', function () {
            setTimeout(function () { self.applyLink(self.urlField.value); }, 0);
        });
        this.urlField.addEventListener('change', function () {
            self.applyLink(self.urlField.value);
        });
        // Enter inside the link field means "use this link", never "submit the
        // profile form" - which is what it would do by default, saving a
        // half-filled location.
        this.urlField.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                self.applyLink(self.urlField.value);
            }
        });
    };

    Picker.prototype.value = function () {
        var lat = parseFloat(this.latInput.value);
        var lng = parseFloat(this.lngInput.value);
        if (!isFinite(lat) || !isFinite(lng)) return null;
        return { lat: lat, lng: lng };
    };

    /* The single write path: everything that changes the location comes through
     * here, so the inputs, the marker and the status line can never disagree. */
    Picker.prototype.set = function (pair, link, opts) {
        opts = opts || {};
        if (pair) {
            // 6dp is ~11cm and matches the Numeric(9,6) columns the values land
            // in; anything beyond it is noise the database would round anyway.
            this.latInput.value = pair.lat.toFixed(6);
            this.lngInput.value = pair.lng.toFixed(6);
        } else {
            this.latInput.value = '';
            this.lngInput.value = '';
        }
        if (link !== undefined) {
            this.linkInput.value = link || '';
            if (opts.syncField !== false) this.urlField.value = link || '';
        }
        this.syncMarker(opts.recenter !== false);
        this.syncStatus(opts.message);
    };

    Picker.prototype.clear = function () {
        this.set(null, '', { recenter: false, message: 'Location cleared.' });
        if (this.map) this.map.setView(DEFAULT_VIEW, DEFAULT_ZOOM);
    };

    Picker.prototype.applyLink = function (text) {
        text = (text || '').trim();
        if (!text) {
            // Emptying the box clears the link but keeps a pin the user may have
            // dropped by hand - those are two independent halves (see maps.py).
            this.linkInput.value = '';
            this.syncStatus();
            return;
        }

        var pair = parseCoordinates(text);
        var isBare = BARE_PAIR.test(text);

        // Anything that is neither coordinates nor a link from a map site is
        // refused here rather than sent on to be rejected server-side. Any pin
        // already dropped survives - the bad paste is the only thing discarded.
        if (!isBare && !isMapHost(text)) {
            this.linkInput.value = '';
            this.syncStatus(pair
                ? 'That does not look like a map link, so it was not saved - your pin is unchanged.'
                : 'That does not look like a Google Maps link. Paste one from the Maps app, or tap the map below.');
            return;
        }

        // A bare "11.55,104.92" paste is coordinates, not a link, so nothing is
        // stored as map_link for it - same rule as maps.resolve().
        var link = isBare ? '' : text;

        if (pair) {
            this.set(pair, link, { syncField: false, message: 'Location set from the link.' });
            return;
        }
        if (isShortLink(text)) {
            this.resolveLink(text);
            return;
        }
        // A map-site link we could not read coordinates out of. Still worth
        // keeping - a human can open it - so say so rather than reject it.
        this.set(this.value(), link, {
            syncField: false,
            message: 'Saved the link. Drag the pin below if you want the exact spot too.'
        });
    };

    /* Short links carry no coordinates until the redirect is followed, and the
     * browser cannot follow it (no CORS headers on goo.gl), so the server does
     * it - see blueprints/maps_routes.py. */
    Picker.prototype.resolveLink = function (text) {
        var self = this;
        this.syncStatus('Looking up that link...');
        fetch('/maps/resolve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: text })
        }).then(function (response) {
            return response.ok ? response.json() : null;
        }).then(function (data) {
            var pair = data && data.latitude !== null && data.longitude !== null
                ? toPair(data.latitude, data.longitude)
                : null;
            self.set(pair, text, {
                syncField: false,
                message: pair
                    ? 'Location set from the link.'
                    : 'Saved the link, but we could not read a pin out of it. Drag the pin below to set the exact spot.'
            });
        }).catch(function () {
            self.set(self.value(), text, {
                syncField: false,
                message: 'Saved the link. We could not check it just now - drag the pin below to set the exact spot.'
            });
        });
    };

    Picker.prototype.useBrowserLocation = function () {
        var self = this;
        if (!navigator.geolocation) {
            this.syncStatus('This browser cannot report your location. Drag the pin instead.');
            return;
        }
        this.syncStatus('Finding your location...');
        navigator.geolocation.getCurrentPosition(function (position) {
            self.set(
                { lat: position.coords.latitude, lng: position.coords.longitude },
                undefined,
                { message: 'Location set from your device. Drag the pin to fine-tune it.' }
            );
        }, function () {
            // Covers a refused permission and a timeout alike - the user does
            // not need them told apart, they need the other way in.
            self.syncStatus('Could not get your location. Drag the pin on the map instead.');
        }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
    };

    // ---- map ---------------------------------------------------------------
    Picker.prototype.ensureMap = function () {
        var self = this;
        if (this.map) return Promise.resolve(this.map);
        return loadLeaflet().then(function (L) {
            if (self.map) return self.map;   // a second ensureMap() raced us
            var start = self.value();
            self.map = L.map(self.mapEl, { scrollWheelZoom: false }).setView(
                start ? [start.lat, start.lng] : DEFAULT_VIEW,
                start ? PIN_ZOOM : DEFAULT_ZOOM
            );
            tileLayer(L).addTo(self.map);

            // Tap/click anywhere to move the pin - on a phone that is far easier
            // than grabbing a marker that is only a few millimetres across.
            self.map.on('click', function (e) {
                self.set({ lat: e.latlng.lat, lng: e.latlng.lng }, undefined, {
                    recenter: false,
                    message: 'Location set. Drag the pin to fine-tune it.'
                });
            });
            self.syncMarker(false);
            return self.map;
        }).catch(function () {
            self.mapEl.classList.add('is-unavailable');
            self.mapEl.textContent = 'The map could not be loaded. You can still paste a Google Maps link above.';
            return null;
        });
    };

    Picker.prototype.syncMarker = function (recenter) {
        var self = this;
        var pair = this.value();
        if (!this.map) {
            if (this.mapReady) this.ensureMap().then(function () { self.syncMarker(recenter); });
            return;
        }
        var L = window.L;
        if (!pair) {
            if (this.marker) { this.map.removeLayer(this.marker); this.marker = null; }
            return;
        }
        if (!this.marker) {
            this.marker = L.marker([pair.lat, pair.lng], {
                draggable: true,
                icon: pinIcon(L)
            }).addTo(this.map);
            this.marker.on('dragend', function () {
                var position = self.marker.getLatLng();
                self.set({ lat: position.lat, lng: position.lng }, undefined, {
                    recenter: false,
                    message: 'Location updated.'
                });
            });
        } else {
            this.marker.setLatLng([pair.lat, pair.lng]);
        }
        if (recenter) this.map.setView([pair.lat, pair.lng], Math.max(this.map.getZoom(), PIN_ZOOM));
    };

    Picker.prototype.syncStatus = function (message) {
        var pair = this.value();
        var link = this.linkInput.value;

        if (message) {
            this.statusEl.textContent = message;
        } else if (pair) {
            this.statusEl.textContent = 'Pinned at ' + pair.lat.toFixed(6) + ', ' + pair.lng.toFixed(6) + '.';
        } else if (link) {
            this.statusEl.textContent = 'A map link is saved for this address.';
        } else {
            this.statusEl.textContent = 'No location set yet.';
        }

        // "Open in Google Maps" is the point of the whole feature for whoever
        // ends up delivering, so it is shown here too - and it prefers the
        // pasted link over the synthesized one, exactly like location_link().
        var href = link || (pair
            ? 'https://www.google.com/maps?q=' + pair.lat.toFixed(6) + ',' + pair.lng.toFixed(6)
            : '');
        if (this.openEl) {
            this.openEl.href = href;
            this.openEl.hidden = !href;
        }
        this.root.classList.toggle('has-location', !!(pair || link));
    };

    /* Called when the picker becomes visible. Leaflet sizes itself from the
     * container at creation time, so one built inside a display:none modal comes
     * out zero-height with a grey void where the tiles should be - this is what
     * the admin modal calls after opening. */
    Picker.prototype.reveal = function () {
        var self = this;
        this.mapReady = true;
        return this.ensureMap().then(function (map) {
            if (!map) return;
            map.invalidateSize();
            var pair = self.value();
            if (pair) map.setView([pair.lat, pair.lng], PIN_ZOOM);
            else map.setView(DEFAULT_VIEW, DEFAULT_ZOOM);
            self.syncMarker(false);
        });
    };

    // ---- registry ----------------------------------------------------------
    var pickers = {};

    function get(id) {
        return pickers[id] || null;
    }

    function init(root) {
        if (!root || root.dataset.locInit) return null;
        root.dataset.locInit = '1';
        var picker = new Picker(root);
        pickers[root.id] = picker;
        return picker;
    }

    window.EBLocationPicker = {
        /* Set up every picker on the page. Ones that are already on screen build
         * their map immediately; ones inside a closed modal wait for reveal(). */
        initAll: function () {
            document.querySelectorAll('.loc-picker').forEach(function (root) {
                var picker = init(root);
                if (picker && root.offsetParent !== null) picker.reveal();
            });
        },
        get: get,
        /* Point a picker at a location from outside - the admin customers modal
         * calls this when it opens on a different customer. */
        setValue: function (id, lat, lng, link) {
            var picker = get(id);
            if (!picker) return;
            var pair = (lat === null || lat === undefined || lat === '') ? null : toPair(lat, lng);
            picker.set(pair, link || '', { recenter: false });
        },
        reveal: function (id) {
            var picker = get(id);
            if (picker) picker.reveal();
        },

        /* A read-only map of one location, for showing where something is going
         * rather than choosing it - the cart drawer draws the customer's saved pin
         * with this. Same tiles and same pin as the picker above, so the little map
         * and the one they edit it in look like the same place.
         *
         * Every interaction is off: at thumbnail size a pannable map is a trap on a
         * phone, and whatever sits over it (the cart's "Open in Google Maps" link)
         * should get the tap. The attribution control stays - it is the one part of
         * an OpenStreetMap map that is not optional.
         *
         * Safe to call repeatedly: the map is built once per element and later calls
         * just move it, which is what makes it cheap to re-run on every render. */
        preview: function (element, latitude, longitude) {
            var pair = toPair(latitude, longitude);
            if (!element || !pair) return Promise.resolve(null);
            return loadLeaflet().then(function (L) {
                var map = element._locPreviewMap;
                if (!map) {
                    map = L.map(element, {
                        zoomControl: false,
                        attributionControl: true,
                        dragging: false,
                        scrollWheelZoom: false,
                        doubleClickZoom: false,
                        boxZoom: false,
                        keyboard: false,
                        touchZoom: false
                    });
                    tileLayer(L).addTo(map);
                    element._locPreviewMap = map;
                }
                map.setView([pair.lat, pair.lng], PREVIEW_ZOOM);
                if (element._locPreviewMarker) {
                    element._locPreviewMarker.setLatLng([pair.lat, pair.lng]);
                } else {
                    element._locPreviewMarker = L.marker([pair.lat, pair.lng], {
                        icon: pinIcon(L),
                        interactive: false
                    }).addTo(map);
                }
                // Leaflet measures its container when the map is created, so one
                // built inside a collapsed section comes out zero-height. Callers
                // re-run this when the section opens; this is what makes that work.
                map.invalidateSize();
                return map;
            }).catch(function () {
                return null;   // no map - the caller falls back to a plain link
            });
        },

        parseCoordinates: parseCoordinates
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', window.EBLocationPicker.initAll);
    } else {
        window.EBLocationPicker.initAll();
    }
})();
