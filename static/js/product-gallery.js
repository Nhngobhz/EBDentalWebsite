/* ============================================================
   PRODUCT-PAGE GALLERY — the thumbnail rail + main stage + full
   screen lightbox shared by products/detail.html (a Product) and
   products/bundle_detail.html (a Promotion or a Set).

   Both pages render the same .pd-gallery markup, so the behaviour
   lives here rather than being pasted into each template:

       PdGallery.init(["/url/one.jpg", "/url/two.jpg", ...]);

   The list is the same one the thumbnails were rendered from, in
   the same order - index N here is the button with data-index="N".
   A page with a single image still works: the arrows wrap around
   to the same photo and the rail is hidden by CSS.
   ============================================================ */
const PdGallery = {
    images: [],
    index: 0,

    init(images) {
        this.images = images || [];
        this.index = 0;
        if (!this.images.length) return;

        document.querySelectorAll('#pdThumbs .pd-thumb').forEach(thumb => {
            const target = Number(thumb.dataset.index);
            // Hovering a thumbnail previews it, the way a marketplace gallery
            // does; the click is what "sticks" for touch and keyboard users.
            thumb.addEventListener('mouseenter', () => this.show(target));
            thumb.addEventListener('click', () => this.show(target));
        });

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
    },

    show(index) {
        if (!this.images.length) return;
        if (index < 0) index = this.images.length - 1;
        if (index >= this.images.length) index = 0;
        this.index = index;

        const main = document.getElementById('pdMainImage');
        if (main) main.src = this.images[this.index];

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
    },

    _paintLightbox() {
        const img = document.getElementById('pdLightboxImage');
        if (img) img.src = this.images[this.index];
        const count = document.getElementById('pdLightboxCount');
        if (count) count.textContent = `${this.index + 1} / ${this.images.length}`;
    },
};
