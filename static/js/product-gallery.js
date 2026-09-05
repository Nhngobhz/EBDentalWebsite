/* ============================================================
   PRODUCT-PAGE GALLERY — the thumbnail rail + main stage + full
   screen lightbox shared by products/detail.html (a Product) and
   products/bundle_detail.html (a Promotion or a Set).

   Both pages render the same .pd-gallery markup, so the behaviour
   lives here rather than being pasted into each template:

       PdGallery.init([{url: "/one.jpg", type: "image"},
                       {url: "/clip.mp4", type: "video"}, ...]);

   The list is the same one the thumbnails were rendered from, in
   the same order - index N here is the button with data-index="N".
   A page with a single item still works: the arrows wrap around
   to the same one and the rail is hidden by CSS.

   Videos are gallery entries like any other (store-api keeps them
   in the same table as the photos - see models.ProductImage), so
   they interleave with the stills wherever they were uploaded.
   The stage holds BOTH an <img> and a <video>; showing one hides
   the other rather than rewriting the markup, so a mis-typed
   entry can never end up with an MP4 in an <img> src.
   ============================================================ */
const PdGallery = {
    items: [],
    index: 0,

    init(items) {
        // Plain strings are still accepted so a caller that hasn't been updated
        // (or a page with no video to describe) keeps working - they mean image.
        this.items = (items || []).map(item =>
            typeof item === 'string' ? { url: item, type: 'image' } : item
        );
        this.index = 0;
        if (!this.items.length) return;

        document.querySelectorAll('#pdThumbs .pd-thumb').forEach(thumb => {
            const target = Number(thumb.dataset.index);
            // Hovering a thumbnail previews it, the way a marketplace gallery
            // does; the click is what "sticks" for touch and keyboard users.
            // Not on a video's thumbnail: hover-swapping onto a clip would stop
            // whatever is playing every time the pointer crossed the rail.
            if (this.items[target]?.type !== 'video') {
                thumb.addEventListener('mouseenter', () => this.show(target));
            }
            thumb.addEventListener('click', () => this.show(target));
        });

        // A video's own frame is its "click to enlarge" target only outside the
        // controls, so the stage listeners are on the image alone - clicking a
        // <video> has to mean play/pause, not "open the lightbox".
        document.getElementById('pdMainImage')?.addEventListener('click', () => this.openLightbox());
        document.getElementById('pdZoomBtn')?.addEventListener('click', () => this.openLightbox());
        document.getElementById('pdLightboxClose')?.addEventListener('click', () => this.closeLightbox());
        document.getElementById('pdLightboxPrev')?.addEventListener('click', () => this.show(this.index - 1));
        document.getElementById('pdLightboxNext')?.addEventListener('click', () => this.show(this.index + 1));

        const box = document.getElementById('pdLightbox');
        box?.addEventListener('click', e => {
            // Only the backdrop closes - clicking the photo or a control shouldn't.
            if (e.target === box) this.closeLightbox();
        });

        document.addEventListener('keydown', e => {
            if (!this.isLightboxOpen()) return;
            if (e.key === 'Escape') this.closeLightbox();
            if (e.key === 'ArrowLeft') this.show(this.index - 1);
            if (e.key === 'ArrowRight') this.show(this.index + 1);
        });

        // Paint once so the stage agrees with the rail on load, including the
        // case where the gallery's first entry is a video.
        this.show(0);
    },

    current() {
        return this.items[this.index];
    },

    show(index) {
        if (!this.items.length) return;
        if (index < 0) index = this.items.length - 1;
        if (index >= this.items.length) index = 0;
        this.index = index;

        const item = this.items[this.index];
        const isVideo = item.type === 'video';

        const image = document.getElementById('pdMainImage');
        const video = document.getElementById('pdMainVideo');
        const zoom = document.getElementById('pdZoomBtn');

        // Moving off a video stops it. Without this the audio keeps running from a
        // stage nobody can see any more, and there is no visible control to stop it.
        if (video && !isVideo) {
            video.pause();
            // Dropping the src as well as hiding it: a paused <video> still holds
            // the buffered file, and these are up to 100MB each.
            video.removeAttribute('src');
            video.load();
        }

        if (image) {
            image.hidden = isVideo;
            if (!isVideo) image.src = item.url;
        }
        if (video) {
            video.hidden = !isVideo;
            if (isVideo) video.src = item.url;
        }
        // "Click to enlarge" is about a photo; a video has its own controls, and the
        // lightbox shows it at the same size the stage already does.
        if (zoom) zoom.hidden = isVideo;

        document.querySelectorAll('#pdThumbs .pd-thumb').forEach((thumb, i) => {
            thumb.classList.toggle('active', i === this.index);
            thumb.setAttribute('aria-selected', i === this.index ? 'true' : 'false');
        });

        if (this.isLightboxOpen()) this._paintLightbox();
    },

    isLightboxOpen() {
        return !!document.getElementById('pdLightbox')?.classList.contains('active');
    },

    openLightbox() {
        const box = document.getElementById('pdLightbox');
        if (!box) return;
        box.classList.add('active');
        document.body.style.overflow = 'hidden';
        this._paintLightbox();
    },

    closeLightbox() {
        document.getElementById('pdLightbox')?.classList.remove('active');
        document.body.style.overflow = '';
        // The stage's own <video> keeps playing behind the lightbox on purpose (it is
        // the same clip the viewer was watching); only the lightbox copy is stopped.
        const video = document.getElementById('pdLightboxVideo');
        if (video) {
            video.pause();
            video.removeAttribute('src');
            video.load();
        }
    },

    _paintLightbox() {
        const item = this.current();
        if (!item) return;
        const isVideo = item.type === 'video';

        const image = document.getElementById('pdLightboxImage');
        if (image) {
            image.hidden = isVideo;
            if (!isVideo) image.src = item.url;
        }
        const video = document.getElementById('pdLightboxVideo');
        if (video) {
            video.hidden = !isVideo;
            if (isVideo) {
                video.src = item.url;
            } else {
                video.pause();
                video.removeAttribute('src');
                video.load();
            }
        }

        const count = document.getElementById('pdLightboxCount');
        if (count) count.textContent = `${this.index + 1} / ${this.items.length}`;
    },
};
