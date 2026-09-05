/* ============================================================
   EB DENTAL SUPPLY — MAIN JS
   ============================================================ */

/* ------------------------------------------------------------
   HERO SLIDER
   Works for any element with class "hero-slider" or
   "product-hero-slider" that follows this structure:

   <section class="hero-slider">
     <div class="slides">
       <div class="slide">...</div>
       <div class="slide">...</div>
     </div>
     <button class="arrow prev">...</button>
     <button class="arrow next">...</button>
     <div class="controls">
       <button class="dot active" data-index="0"></button>
       <button class="dot" data-index="1"></button>
     </div>
   </section>

   NOTE: This slider logic did not exist in the original file —
   the HTML/CSS were built for it, but the JS was never written.
   This is new code finishing that feature.
------------------------------------------------------------- */

function initHeroSlider(sliderEl) {
    const track = sliderEl.querySelector('.slides');
    const slides = sliderEl.querySelectorAll('.slide');
    const prevBtn = sliderEl.querySelector('.arrow.prev');
    const nextBtn = sliderEl.querySelector('.arrow.next');
    const dots = sliderEl.querySelectorAll('.dot');

    if (!track || slides.length === 0) return;

    let currentIndex = 0;
    const totalSlides = slides.length;
    const AUTOPLAY_DELAY = 5000;
    let autoplayTimer = null;

    function goToSlide(index) {
        currentIndex = (index + totalSlides) % totalSlides;
        track.style.transform = `translateX(-${currentIndex * 100}%)`;

        dots.forEach((dot, i) => {
            dot.classList.toggle('active', i === currentIndex);
        });
        // Drives the slow Ken Burns zoom + content fade-up on the visible
        // slide only (see .hero-slider .slide.active in home.css) — restarting
        // the CSS animation each time by toggling the class off then on.
        slides.forEach((slide, i) => {
            if (i === currentIndex) {
                slide.classList.remove('active');
                void slide.offsetWidth; // force reflow so the animation restarts
                slide.classList.add('active');
            } else {
                slide.classList.remove('active');
            }
        });
    }

    function nextSlide() {
        goToSlide(currentIndex + 1);
    }

    function prevSlide() {
        goToSlide(currentIndex - 1);
    }

    function startAutoplay() {
        stopAutoplay();
        autoplayTimer = setInterval(nextSlide, AUTOPLAY_DELAY);
    }

    function stopAutoplay() {
        if (autoplayTimer) clearInterval(autoplayTimer);
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            nextSlide();
            startAutoplay(); // reset timer on manual interaction
        });
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            prevSlide();
            startAutoplay();
        });
    }

    dots.forEach((dot, i) => {
        dot.addEventListener('click', () => {
            goToSlide(i);
            startAutoplay();
        });
    });

    // Pause autoplay while the user's mouse is over the slider
    sliderEl.addEventListener('mouseenter', stopAutoplay);
    sliderEl.addEventListener('mouseleave', startAutoplay);

    goToSlide(0);
    startAutoplay();
}

/* ------------------------------------------------------------
   INIT — runs once the page has loaded
------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.hero-slider, .product-hero-slider').forEach(initHeroSlider);
});

/* ------------------------------------------------------------
   SCROLL REVEAL — see .reveal/.reveal-stagger in base.css.
   Progressive enhancement: if IntersectionObserver isn't available,
   everything is just revealed immediately instead of staying hidden.
------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    const revealEls = document.querySelectorAll('.reveal, .reveal-stagger');
    if (!revealEls.length) return;

    if (!('IntersectionObserver' in window)) {
        revealEls.forEach(el => el.classList.add('is-visible'));
        return;
    }

    const io = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                io.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12, rootMargin: '0px 0px -60px 0px' });

    revealEls.forEach(el => io.observe(el));
});

/* ------------------------------------------------------------
   ADMIN SIDEBAR — collapsible section groups
   Each group (Overview, Catalog, User Management, etc.) toggles
   independently — not an accordion, multiple can stay open at once.
------------------------------------------------------------- */
function toggleGroup(groupId) {
    const container = document.getElementById(groupId);
    if (!container) return;
    container.classList.toggle('open');
    const icon = container.closest('.nav-group').querySelector('.group-icon');
    if (icon) icon.classList.toggle('open');
}

/* ------------------------------------------------------------
   ADMIN DASHBOARD — mobile sidebar toggle
   The sidebar hides off-screen under 768px width (see dashboard.css);
   the hamburger button opens it, the X button or tapping the dark
   backdrop closes it again (hamburger gets covered once it's open).
------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    const menuToggle = document.getElementById('dashMenuToggle');
    const sidebar = document.getElementById('dashSidebar');
    const closeBtn = document.getElementById('dashSidebarClose');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (!sidebar) return;

    function openSidebar() {
        sidebar.classList.add('open');
        if (backdrop) backdrop.classList.add('active');
    }
    function closeSidebar() {
        sidebar.classList.remove('open');
        if (backdrop) backdrop.classList.remove('active');
    }

    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
        });
    }
    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (backdrop) backdrop.addEventListener('click', closeSidebar);
});

/* ------------------------------------------------------------
   HOT SELLING CAROUSEL — prev/next scroll buttons
   The carousel itself scrolls natively (CSS scroll-snap); these
   buttons just nudge it left/right by roughly one card's width.
------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    const track = document.getElementById('hotCarouselTrack');
    const prevBtn = document.getElementById('hotPrev');
    const nextBtn = document.getElementById('hotNext');
    if (!track) return;

    function scrollByOneCard(direction) {
        const card = track.querySelector('.offer-card, .product-card');
        const cardWidth = card ? card.getBoundingClientRect().width + 12 : track.clientWidth * 0.9;
        track.scrollBy({ left: direction * cardWidth, behavior: 'smooth' });
    }

    if (prevBtn) prevBtn.addEventListener('click', () => scrollByOneCard(-1));
    if (nextBtn) nextBtn.addEventListener('click', () => scrollByOneCard(1));
});

/* ------------------------------------------------------------
   CATALOG FILTERS — the category strip across the top of
   /products and the standing category panel down its left side.
   See templates/products/catalog.html.

   Both controls are plain links/checkboxes that work with the page
   reloading and no JS at all; everything here is enhancement:
   folding the long category strip away, and turning a tick in the
   panel into a navigation so the Apply button isn't needed.
------------------------------------------------------------- */
function initCatalogFilters() {
    const strip = document.getElementById('catStrip');
    const sidebar = document.getElementById('catalogSidebar');

    if (strip) {
        const row = document.getElementById('catStripRow');
        const moreBtn = document.getElementById('catStripMore');
        // How much of the edge softens where the row runs off the side. Matches
        // the --fade-l/--fade-r stops in products.css.
        const FADE = '34px';

        function isOpen() {
            return strip.classList.contains('is-open');
        }

        // The width one unwrapped row of names would take. Summed from the
        // links rather than read off scrollWidth, because scrollWidth answers
        // the question only while the row is NOT wrapped - and this is asked in
        // both states, to decide whether the chevron has anything to reveal.
        // (An earlier version measured height instead and hid the chevron the
        // moment you used it, because clientHeight mid-animation reported the
        // strip as already showing everything.)
        function naturalRowWidth() {
            const links = row.children;
            if (!links.length) return 0;
            const colGap = parseFloat(getComputedStyle(row).columnGap) || 0;
            let total = colGap * (links.length - 1);
            for (const link of links) total += link.getBoundingClientRect().width;
            return total;
        }

        // Chevron only where it does something: with every category already on
        // screen there is no "rest" to drop down to.
        function syncOverflow() {
            // 4px of slack for sub-pixel widths, which otherwise report a few
            // hundredths of overflow on a strip that fits perfectly.
            strip.classList.toggle(
                'no-overflow', naturalRowWidth() <= row.clientWidth + 4
            );
        }

        // The edge fades, in whichever direction the strip currently runs.
        // Closed that is sideways - one fade per end, each shown only while
        // there is actually more list past it. Open it is downwards, and the
        // same reasoning applies to the bottom edge.
        function syncFades() {
            if (isOpen()) {
                const below = row.scrollHeight - row.clientHeight - row.scrollTop;
                strip.classList.toggle('is-clipped', below > 4);
                return;
            }
            strip.classList.remove('is-clipped');
            const right = row.scrollWidth - row.clientWidth - row.scrollLeft;
            row.style.setProperty('--fade-l', row.scrollLeft > 4 ? FADE : '0px');
            row.style.setProperty('--fade-r', right > 4 ? FADE : '0px');
        }
        row.addEventListener('scroll', syncFades, { passive: true });

        // Everything that can't ride along on the class change, because it is
        // either not an animatable property or would fight the animation:
        //
        //  - overflow-y, switched on only once the panel has finished growing.
        //    Turned on at the start, the scrollbar draws over a panel that is
        //    still growing and then disappears again if the names turn out to
        //    fit inside the cap.
        //  - .is-closing, which holds the wrapped layout until the panel has
        //    finished folding away. Without it the row snaps back to one line
        //    immediately and there is nothing left for max-height to animate.
        //
        // A timer rather than `transitionend`, because transitionend never
        // fires when the transition is suppressed (reduced-motion settings, a
        // background tab) - and the strip would then be stuck wrapped, clipped,
        // and unscrollable, which is far worse than a slightly early scrollbar.
        let phaseTimer;
        function setOpenState(open) {
            clearTimeout(phaseTimer);
            if (open) {
                strip.classList.remove('is-closing');
                phaseTimer = setTimeout(() => {
                    strip.classList.add('is-scrollable');
                    syncFades();
                }, 360);
            } else {
                strip.classList.remove('is-scrollable');
                strip.classList.add('is-closing');
                // Back to the top, or the one row left visible after closing is
                // wherever the reader had scrolled to - the strip would collapse
                // onto "Intraoral Scanner ... Mobile Cart" with no All link and
                // no sign it had been scrolled at all.
                row.scrollTop = 0;
                phaseTimer = setTimeout(() => {
                    strip.classList.remove('is-closing');
                    // Only now is the row one line again, so only now can it be
                    // asked how far off the side it runs.
                    syncFades();
                    revealActive();
                }, 360);
            }
            syncFades();
        }

        if (moreBtn) {
            moreBtn.addEventListener('click', () => {
                const open = strip.classList.toggle('is-open');
                moreBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
                moreBtn.setAttribute(
                    'aria-label', open ? 'Show fewer categories' : 'Show all categories'
                );
                setOpenState(open);
            });
        }

        // A ticked category should be on screen without having to hunt for it -
        // otherwise a filter can be active with no sign of it in the strip. The
        // STRIP is scrolled, never the window: the shopper is at the top of the
        // page and should stay there.
        function revealActive() {
            const active = row.querySelector('.cat-strip-link.active:not(:first-child)');
            if (!active || isOpen()) return;
            const rowBox = row.getBoundingClientRect();
            const box = active.getBoundingClientRect();
            // The least scrolling that brings the whole name inside the row -
            // a category near the end then sits at the right-hand edge rather
            // than being dragged all the way to the left.
            if (box.right > rowBox.right) {
                row.scrollLeft += box.right - rowBox.right + 24;
            } else if (box.left < rowBox.left) {
                row.scrollLeft += box.left - rowBox.left - 24;
            }
        }

        function syncAll() {
            syncOverflow();
            // Smooth scrolling is what the strip wants for a swipe, but not for
            // a correcting jump - the names would visibly slide past on load.
            row.style.scrollBehavior = 'auto';
            revealActive();
            row.style.scrollBehavior = '';
            syncFades();
        }

        syncAll();
        // ...and again once the web fonts have landed. Every answer above is a
        // measurement of text, and this runs on DOMContentLoaded, with Inter
        // still loading: against the fallback metrics the strip measured ~1000px
        // narrower than it ends up, so the jump to a ticked category stopped
        // short of it and the chevron was decided on a layout about to change.
        if (document.fonts && document.fonts.ready) {
            document.fonts.ready.then(syncAll);
        }

        // How many names fit across is a width question, so it has to be
        // re-asked when the window changes.
        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                syncOverflow();
                syncFades();
            }, 150);
        });
    }

    if (sidebar) {
        // Ticking a box navigates to that box's toggle URL - the exact same URL
        // the matching text link in the strip points at, so the two controls
        // can't disagree about what a category click means. The form around
        // them stays a real GET form for the no-JS path (.cs-apply, hidden by
        // CSS once .has-js is on the document).
        sidebar.querySelectorAll('.cs-item input[type="checkbox"]').forEach((box) => {
            box.addEventListener('change', () => {
                const href = box.dataset.href;
                if (href) window.location.href = href;
            });
        });
    }
}

document.addEventListener('DOMContentLoaded', initCatalogFilters);

/* ------------------------------------------------------------
   BRAND STRIP — the row of brand pills across the top of both
   catalogs (.eb-brand-* in products.css; the materials catalog
   scales the same control up in materials.css).

   The row scrolls natively, so a swipe or a trackpad has always
   worked; the two arrows beside it never did anything, which on
   the materials strip - ten brands, wider pills - is a control
   the shopper actually needs. Everything here is that: how far a
   press moves the row, whether either end has been reached, and
   whether the row overflows at all. Nothing here filters
   anything - every pill is a plain link the server answers, and
   with no JS the arrows simply sit there as before.
------------------------------------------------------------- */
function initBrandScrollers() {
    // 4px of slack for sub-pixel widths - the same allowance the category strip
    // makes. Without it a row that fits exactly reports a fraction of overflow
    // and keeps two arrows that cannot move it.
    const SLACK = 4;

    document.querySelectorAll('.eb-brand-scroll-container').forEach((container) => {
        const row = container.querySelector('.eb-brand-scroll');
        if (!row) return;
        const prev = container.querySelector('.eb-scroll-arrow.prev');
        const next = container.querySelector('.eb-scroll-arrow.next');

        function sync() {
            const overflow = row.scrollWidth - row.clientWidth;
            // Four brands on a desktop machinery page fit with room to spare, and
            // arrows that cannot move anything read as a broken control - so the
            // whole gutter goes with them. See .no-scroll in products.css.
            container.classList.toggle('no-scroll', overflow <= SLACK);
            if (prev) prev.classList.toggle('disabled', row.scrollLeft <= SLACK);
            if (next) next.classList.toggle('disabled', overflow - row.scrollLeft <= SLACK);
        }

        function nudge(direction) {
            // Most of a screenful rather than all of it: a pill or two stays put,
            // so the row reads as having moved and not as having been replaced.
            row.scrollBy({ left: direction * row.clientWidth * 0.8, behavior: 'smooth' });
        }

        if (prev) prev.addEventListener('click', () => nudge(-1));
        if (next) next.addEventListener('click', () => nudge(1));
        row.addEventListener('scroll', sync, { passive: true });

        // The chosen brand on screen without hunting for it. It is pinned to the
        // front of the materials rail so it usually already is, but a pill can
        // still start off the side on a narrow screen - and a filter you cannot
        // see is one nobody can take off. The ROW scrolls, never the window.
        const active = row.querySelector('.brand-card.active:not(:first-child)');
        if (active) {
            const rowBox = row.getBoundingClientRect();
            const box = active.getBoundingClientRect();
            // Smooth scrolling is what the row wants for a swipe, not for a
            // correcting jump on load - the pills would visibly slide past.
            row.style.scrollBehavior = 'auto';
            if (box.right > rowBox.right) {
                row.scrollLeft += box.right - rowBox.right + 24;
            } else if (box.left < rowBox.left) {
                row.scrollLeft += box.left - rowBox.left - 24;
            }
            row.style.scrollBehavior = '';
        }

        sync();
        // ...and again once the web fonts have landed. Every measurement above is
        // of text, and this runs on DOMContentLoaded with Inter still loading, so
        // the row is about to get wider than it just reported.
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(sync);

        // How many pills fit across is a width question, so it is re-asked
        // whenever the window changes.
        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(sync, 150);
        });
    });
}

document.addEventListener('DOMContentLoaded', initBrandScrollers);

/* NOTE: subcategory add/remove logic now lives inline in brands.html's
   modal (page-specific), not here globally — avoids double-registering
   the same button when the modal script also wires it up. */

/* ------------------------------------------------------------
   PRICE FORMATTING — store-api masks price/discount as the
   literal string "XXXX" for viewers without price access (see
   formatting.py's format_price() on the Flask side, which is
   what already ran on anything reaching a *_DATA blob or an
   inline product object before this runs).
------------------------------------------------------------- */
function formatPrice(value) {
    if (value === 'XXXX') return 'Login to view price';
    if (typeof value !== 'number') return '';
    return '$' + value.toFixed(2);
}

/* A per-product/per-order-item discount is either a percent or a flat $ amount, per
   discount_type (see Product.discount_type / OrderItem.discount_type). Used anywhere a
   line-item discount is displayed: the quote drawer, the printed quote, and the admin
   Orders view modal. Returns null (not a placeholder string) when there's no discount,
   so callers can decide their own "no discount" wording. */
function formatItemDiscount(discount, discountType) {
    if (!discount) return null;
    return discountType === 'cash' ? '$' + Number(discount).toFixed(2) : Number(discount) + '%';
}

/* A line's undiscounted unit price, i.e. the "UP before Discount" column on the
   printed quote and the Sub-Total/Discount breakdown in the admin Orders modal.

   This now READS the figure (OrderItem.list_price, snapshotted server-side when the
   order was placed) instead of reconstructing it as unit_price / (1 - discount/100).
   The old reconstruction existed only because store-api stored no original price;
   three separate copies of it had to agree, and it silently changed whenever a price
   was edited. See store-api's f2a9c4e18b73 migration.

   `item` is an OrderItem as returned by store-api. The fallback to unit_price covers
   a line whose list_price didn't come through (an older cached payload), where "no
   discount" is the right thing to show rather than NaN. */
function deriveOldUnitPrice(item) {
    const listPrice = Number(item.list_price);
    const unitPrice = Number(item.unit_price);
    return Number.isFinite(listPrice) && listPrice > unitPrice ? listPrice : unitPrice;
}

/* Printed quote/invoice item table only (buildPrintTemplate + the admin Orders view
   modal) - NOT the live Cart drawer, which still shows every item's real discount/price
   as it builds the order. In the printed table, a $ (cash) item discount is rolled into
   the combined "Discount($)" total row instead of being called out per-item, so that
   row's own Discount column goes blank and its Amount shows the undiscounted price -
   only a % discount still displays inline on its own row. */
function printedItemDiscountText(item) {
    return item.discount_type === 'percent' ? formatItemDiscount(item.discount, item.discount_type) : null;
}

function printedItemAmount(item) {
    return item.discount_type === 'cash'
        ? deriveOldUnitPrice(item) * item.qty
        : Number(item.line_amount);
}

/* The printed "Discount($)" total row is ONLY the money saved by $ (cash) item
   discounts - a % item discount is already visible inline on its own row (see
   printedItemDiscountText/printedItemAmount above), so folding it into this aggregate
   too would double-count the same discount both per-row and in the total. */
function printedCashDiscountTotal(items) {
    return items.reduce((sum, item) => {
        if (item.discount_type !== 'cash') return sum;
        const oldUnitPrice = deriveOldUnitPrice(item);
        return sum + (oldUnitPrice - Number(item.unit_price)) * item.qty;
    }, 0);
}

/* A promotion/set is a collection of products, and a product may come with
   freebies - both arrive from store-api in the same {product_name, product_code,
   uom, qty} shape (BundleItemOut). Flattened here to the cart's own field names
   so a cart line doesn't have to remember which of the two it came from.

   `qty` is PER ONE of the parent line: 3 gloves in a set means 6 gloves when two
   of that set are bought. The cart multiplies for display; store-api does the
   same multiplication for real when the order is placed (see _component_items in
   routers/orders.py) - these local copies are never trusted for the actual order. */
function normalizeBundleComponents(items) {
    return (items || []).map(item => ({
        name: item.product_name,
        code: item.product_code || '',
        uom: item.uom || '',
        qty: item.qty || 1,
    }));
}

/* ============================================================
   QUOTE CART — new feature.
   The original "Add to Quote" button existed with zero logic
   behind it. This whole block makes it actually work: add/remove
   items, adjust quantity, auto-calculate the total, persisted in
   localStorage so it survives page navigation and reloads.

   Adding an item is gated by CAN_QUOTE (see base.html/auth.py) -
   only a VIP customer or price_listing/product_management staff
   may quote at all, and only ever on a real numeric price, never
   the masked "XXXX" sentinel. Finalizing the drawer now also
   submits the cart to POST /quote/submit, which creates a real
   store-api Order (server-priced, never trusting these local
   numbers) before generating the PDF - see confirmPurchase().
   ============================================================ */
const QuoteCart = {
    STORAGE_KEY: 'eb_quote_cart',
    INFO_KEY: 'eb_quote_customer_info',
    DISCOUNT_TYPE_KEY: 'eb_quote_discount_type',
    DISCOUNT_VALUE_KEY: 'eb_quote_discount_value',

    // ---- line items ----
    getItems() {
        try {
            const items = JSON.parse(localStorage.getItem(this.STORAGE_KEY)) || [];
            // 'kind' distinguishes a product line from a promotion line (product ids
            // and promotion ids come from separate tables and can collide) - default it
            // for anything saved before this field existed. 'components' (what the line
            // includes for free) gets the same treatment.
            return items.map(i => ({ ...i, kind: i.kind || 'product', components: i.components || [] }));
        } catch {
            return [];
        }
    },

    saveItems(items) {
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(items));
    },

    clearDraft() {
        localStorage.removeItem(this.STORAGE_KEY);
        localStorage.removeItem(this.INFO_KEY);
        localStorage.removeItem(this.DISCOUNT_TYPE_KEY);
        localStorage.removeItem(this.DISCOUNT_VALUE_KEY);
    },

    // `qty` is how many the product page's quantity selector asked for; every other
    // caller adds one at a time and can leave it out.
    addItem(product, qty = 1) {
        // Belt-and-suspenders: CAN_QUOTE should already have kept the "Add to
        // Quote" control from ever being wired up to a disallowed viewer (see
        // products/detail.html), and a masked price is never a real number - so
        // nothing here should ever be reachable with a bad price, but nothing
        // downstream should have to assume that either.
        if (typeof CAN_QUOTE !== 'undefined' && !CAN_QUOTE) return;
        if (typeof product.price !== 'number') return;

        qty = Math.max(1, Math.floor(Number(qty) || 1));

        // Always appends to whatever is already in the cart - a normal cart never
        // wipes itself out when you add a second product.
        const items = this.getItems();
        const existing = items.find(i => i.id === product.id && i.kind === 'product');
        if (existing) {
            existing.qty += qty;
        } else {
            // Code, UOM, and discount come straight from the product record
            // (set by admin) — salespeople only ever adjust qty on the quote.
            // was_price is the product's stored list_price when it exceeds what's
            // charged (see formatting.py's was_price); price is what's actually
            // charged, with the admin's discount already applied.
            items.push({
                kind: 'product',
                id: product.id,
                name: product.product_name,
                code: product.code || product.product_code || '',
                uom: product.uom || 'PCS',
                price: product.price,
                oldPrice: product.was_price || product.price,
                discount: product.discount || 0,
                discountType: product.discount_type || 'percent',
                image: product.image || '',
                qty,
                // Freebies that ride along with this product, shown under the
                // line in the drawer and on the printed quote at $0.00.
                components: normalizeBundleComponents(product.free_items),
            });
        }
        this.saveItems(items);
        this.render();
    },

    // A Promotion (homepage/promotions-page marketing deal) is bought the same way as
    // a product - see promo.id, which lives in a separate table from Product.id and
    // can collide with it, hence 'kind' to disambiguate cart lookups.
    addPromotion(promo, qty = 1) {
        if (typeof CAN_QUOTE !== 'undefined' && !CAN_QUOTE) return;
        if (typeof promo.price !== 'number') return;

        qty = Math.max(1, Math.floor(Number(qty) || 1));

        const items = this.getItems();
        const existing = items.find(i => i.id === promo.id && i.kind === 'promotion');
        if (existing) {
            existing.qty += qty;
        } else {
            const oldPrice = typeof promo.old_price === 'number' ? promo.old_price : promo.price;
            // Reproduces old_price as a cash "discount" (see routers/orders.py's
            // create_order) so the existing deriveOldUnitPrice() math shows it the
            // same way a product's own discount is shown - no separate code path.
            const discount = oldPrice > promo.price ? oldPrice - promo.price : 0;
            items.push({
                kind: 'promotion',
                id: promo.id,
                name: promo.promotion_name,
                code: '',
                uom: '',
                price: promo.price,
                oldPrice: oldPrice,
                discount: discount,
                discountType: 'cash',
                image: promo.image || '',
                qty,
                // The products the deal is made of - listed under it at $0.00.
                components: normalizeBundleComponents(promo.items),
            });
        }
        this.saveItems(items);
        this.render();
    },

    // A Set (Promotions-page bundle deal) is bought the same way a Promotion is - see
    // set.id, which lives in a separate table from Product.id/Promotion.id and can
    // collide with either, hence 'kind' to disambiguate cart lookups.
    // `options` is [{group_id, choice_id}] for a configurable set - which
    // alternative each swappable slot landed on (see SetOptionGroup in store-api).
    // `set.price` must ALREADY include the chosen upcharges: the set page adds
    // them up as the radios are clicked, and store-api recomputes the same figure
    // from the ids server-side, so a tampered price here changes nothing.
    addSet(set, qty = 1, options = []) {
        if (typeof CAN_QUOTE !== 'undefined' && !CAN_QUOTE) return;
        if (typeof set.price !== 'number') return;

        qty = Math.max(1, Math.floor(Number(qty) || 1));
        const optKey = QuoteCart.optionsKey(options);

        const items = this.getItems();
        // Same set at a DIFFERENT configuration is a different line - merging a
        // $2,000 standard build into an upgraded one would quietly overcharge for
        // the first and undercharge for the second.
        const existing = items.find(
            i => i.id === set.id && i.kind === 'set' && (i.optKey || '') === optKey
        );
        if (existing) {
            existing.qty += qty;
        } else {
            const oldPrice = typeof set.old_price === 'number' ? set.old_price : set.price;
            const discount = oldPrice > set.price ? oldPrice - set.price : 0;
            items.push({
                kind: 'set',
                id: set.id,
                name: set.set_name,
                code: '',
                uom: '',
                price: set.price,
                oldPrice: oldPrice,
                discount: discount,
                discountType: 'cash',
                image: set.image || '',
                qty,
                components: normalizeBundleComponents(set.items),
                options: options || [],
                optKey,
            });
        }
        this.saveItems(items);
        this.render();
    },

    // A stable signature for one configuration, so two carts lines can be told
    // apart (and matched again on qty/remove) without comparing arrays by hand.
    // Sorted so the same picks made in a different order collapse to one key.
    optionsKey(options) {
        return (options || [])
            .map(o => `${o.group_id}:${o.choice_id}`)
            .sort()
            .join('|');
    },

    // optKey narrows to ONE configuration of a set (see addSet). Omitted by the
    // product/promotion callers, where it is always '' on both sides.
    removeItem(id, kind, optKey) {
        kind = kind || 'product';
        optKey = optKey || '';
        this.saveItems(this.getItems().filter(
            i => !(i.id === id && i.kind === kind && (i.optKey || '') === optKey)
        ));
        this.render();
    },

    // Salespeople can only adjust quantity on the quote — code, UOM, unit
    // price, and discount are all admin-set on the product/promotion and shown
    // read-only here. Updates the row's amount + totals directly via the
    // DOM rather than a full render(), so nothing else in the drawer flickers.
    changeQty(id, delta, kind, optKey) {
        kind = kind || 'product';
        optKey = optKey || '';
        const items = this.getItems();
        const item = items.find(
            i => i.id === id && i.kind === kind && (i.optKey || '') === optKey
        );
        if (!item) return;
        item.qty = Math.max(1, item.qty + delta);
        this.saveItems(items);

        const qtyEl = document.querySelector(`.quote-item[data-id="${id}"][data-kind="${kind}"] .quote-qty-value`);
        if (qtyEl) qtyEl.textContent = item.qty;

        const amountEl = document.querySelector(`.quote-item[data-id="${id}"][data-kind="${kind}"] .quote-item-amount`);
        if (amountEl) amountEl.textContent = '$' + this.lineAmount(item).toFixed(2);

        // Included items scale with the line - two of a set means two of
        // everything in it. data-unit-qty is the per-one quantity (see
        // normalizeBundleComponents), so this stays right on repeated clicks.
        document.querySelectorAll(
            `.quote-item[data-id="${id}"][data-kind="${kind}"] .included-qty`
        ).forEach(el => {
            el.textContent = '×' + (Number(el.dataset.unitQty || 1) * item.qty);
        });

        this.updateSummary();
    },

    lineAmount(item) {
        // The admin form already saves the final unit price after any
        // configured discount, so applying the same percentage again here
        // would double-discount the line item in the quote drawer.
        return item.price * item.qty;
    },

    getTotal() {
        return this.getItems().reduce((sum, i) => sum + this.lineAmount(i), 0);
    },

    // ---- Sub-Total (undiscounted) / Discount (product-level money saved) ----
    // Sub-Total is the combined list price before each product's own discount; Discount
    // is the money that discount actually saved. getTotal() above (the charged total)
    // stays == Sub-Total - Discount, so Grand Total's math is unaffected by this split -
    // it's purely a display breakdown.
    //
    // Reads each line's own `oldPrice` (captured from the product's list_price, or a
    // bundle's old_price, when it was added to the cart) rather than dividing the
    // discount back out of `price`.
    getUndiscountedTotal() {
        return this.getItems().reduce(
            (sum, i) => sum + (i.oldPrice > i.price ? i.oldPrice : i.price) * i.qty, 0
        );
    },

    getItemDiscountTotal() {
        return Math.max(0, this.getUndiscountedTotal() - this.getTotal());
    },

    getCount() {
        return this.getItems().reduce((sum, i) => sum + i.qty, 0);
    },

    // ---- order-level discount (percent or cash) ----
    // Separate from each product's own % discount (already baked into its unit price by
    // admin). Setting one at all is staff-only (product_management) - the edit button in
    // quote_drawer.html only renders for staff who hold it, and the server independently
    // enforces the same rule (see routers/orders.py::create_order) since this is only a
    // client-side preview, not the source of truth. CAN_DISCOUNT (set in base.html) is
    // checked here too so a stale stored value from an earlier session can never display
    // or submit a discount for a viewer who isn't currently allowed to set one.
    getDiscountType() {
        if (typeof CAN_DISCOUNT !== 'undefined' && !CAN_DISCOUNT) return 'percent';
        const v = localStorage.getItem(this.DISCOUNT_TYPE_KEY);
        return v === 'cash' ? 'cash' : 'percent';
    },

    saveDiscountType(value) {
        localStorage.setItem(this.DISCOUNT_TYPE_KEY, value === 'cash' ? 'cash' : 'percent');
        this.updateSummary();
    },

    getDiscountValue() {
        if (typeof CAN_DISCOUNT !== 'undefined' && !CAN_DISCOUNT) return 0;
        const v = parseFloat(localStorage.getItem(this.DISCOUNT_VALUE_KEY));
        return Number.isNaN(v) ? 0 : Math.max(0, v);
    },

    saveDiscountValue(value) {
        const v = Math.max(0, parseFloat(value) || 0);
        localStorage.setItem(this.DISCOUNT_VALUE_KEY, String(v));
        this.updateSummary();
    },

    // A Promotion/Set line carries a fixed deal price - the order-level discount below
    // never applies to it, mirroring create_order's discountable_subtotal server-side.
    getDiscountableTotal() {
        return this.getItems().reduce(
            (sum, i) => sum + (i.kind === 'product' ? this.lineAmount(i) : 0), 0
        );
    },

    getDiscountAmount() {
        const base = this.getDiscountableTotal();
        const value = this.getDiscountValue();
        if (this.getDiscountType() === 'percent') return base * Math.min(value, 100) / 100;
        return Math.min(value, base);
    },

    getGrandTotal() {
        return Math.max(0, this.getTotal() - this.getDiscountAmount());
    },

    updateSummary() {
        const badge = document.getElementById('quoteCartBadge');
        const count = this.getCount();
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }

        const subTotalEl = document.getElementById('quoteSubTotal');
        if (subTotalEl) subTotalEl.textContent = '$' + this.getUndiscountedTotal().toFixed(2);

        const itemDiscountEl = document.getElementById('quoteItemDiscount');
        if (itemDiscountEl) itemDiscountEl.textContent = '$' + this.getItemDiscountTotal().toFixed(2);

        const discountAmountEl = document.getElementById('quoteDiscountAmount');
        if (discountAmountEl) discountAmountEl.textContent = '$' + this.getDiscountAmount().toFixed(2);

        const grandTotalEl = document.getElementById('quoteGrandTotal');
        if (grandTotalEl) grandTotalEl.textContent = '$' + this.getGrandTotal().toFixed(2);
    },

    // ---- customer / quote info ----
    getInfo() {
        try {
            return JSON.parse(localStorage.getItem(this.INFO_KEY)) || {};
        } catch {
            return {};
        }
    },

    saveInfoField(field, value) {
        const info = this.getInfo();
        info[field] = value;
        localStorage.setItem(this.INFO_KEY, JSON.stringify(info));
    },

    // ---- auto-fill from the customer's own profile ----
    // The cart's info form is normally restored from localStorage (getInfo).
    // For a signed-in customer the first fill comes from their account instead,
    // so buying something doesn't mean retyping the clinic name, phone and
    // address they already gave us - and so the address the order records is the
    // same one their delivery pin points at.
    //
    // Fetched on first drawer open rather than on page load: a customer who
    // never opens the cart never pays for the request. Cached in a promise for
    // the rest of the page's life, exactly like _ensurePdfLibs().
    _prefillPromise: null,
    ensurePrefill() {
        // Staff are quoting for OTHER clinics - seeding their cart from their own
        // staff record would be wrong every time (see /quote/prefill).
        if (typeof IS_LOGGED_IN === 'undefined' || !IS_LOGGED_IN) return Promise.resolve(null);
        if (typeof IS_STAFF !== 'undefined' && IS_STAFF) return Promise.resolve(null);
        if (this._prefillPromise) return this._prefillPromise;

        this._prefillPromise = fetch(QUOTE_PREFILL_URL, { headers: { 'Accept': 'application/json' } })
            .then(response => (response.ok ? response.json() : null))
            .then(data => {
                this.applyPrefill(data);
                return data;
            })
            // A profile we could not fetch just means the form starts empty, the
            // way it always used to. Never block opening the cart on it.
            .catch(() => null);
        return this._prefillPromise;
    },

    /* Fills the blanks - and only the blanks. Anything already typed into the
     * cart is the customer's more recent intent than their stored profile, so a
     * saved value never overwrites it. */
    applyPrefill(data) {
        if (!data) return;
        const info = this.getInfo();
        [['clinic', 'qiClinic'], ['tel', 'qiTel'], ['address', 'qiAddress']].forEach(([key, id]) => {
            if (info[key] || !data[key]) return;
            const el = document.getElementById(id);
            if (el) el.value = data[key];
            // Written through saveInfoField because setting .value from script
            // fires no `input` event, and submit() reads localStorage, not the DOM.
            this.saveInfoField(key, data[key]);
        });
        this.rememberLocation(data);
    },

    /* The customer's saved pin, as the last server answer described it. Held here
     * rather than read out of the picker's own inputs because the picker only
     * exists once the modal has been opened, and the line under the address box
     * has to be right before that. */
    savedLocation: null,

    rememberLocation(data) {
        this.savedLocation = {
            latitude: (data && data.latitude !== undefined) ? data.latitude : null,
            longitude: (data && data.longitude !== undefined) ? data.longitude : null,
            map_link: (data && data.map_link) || '',
            map_url: (data && data.map_url) || '',
        };
        this.renderSavedLocation();
    },

    /* The map under the address box, and the line that says what it is. Its job
     * is to make the auto-fill visible: a pin the customer cannot see is one
     * they will never notice is wrong or missing - which is why this shows the
     * place rather than linking to it. */
    renderSavedLocation() {
        const wrap = document.getElementById('quoteInfoLocation');
        if (!wrap) return;   // staff drawer - the block isn't rendered at all
        const saved = this.savedLocation || {};
        const mapUrl = saved.map_url || '';
        const text = document.getElementById('quoteInfoLocationText');
        const view = document.getElementById('quoteInfoLocationView');
        const edit = document.getElementById('quoteInfoLocationEdit');

        const drewMap = this.renderLocationPreview(saved, mapUrl);
        if (mapUrl) {
            text.textContent = 'Delivering to your saved location.';
            view.href = mapUrl;
            // Only stands in for a preview we could not draw - a saved map link with
            // no readable coordinates behind it (see maps.py on why those are two
            // independent halves).
            view.hidden = drewMap;
            edit.textContent = 'Change';
        } else {
            text.textContent = 'No delivery location saved yet.';
            view.hidden = true;
            edit.textContent = 'Set one';
        }
        wrap.classList.toggle('is-missing', !mapUrl);
        wrap.hidden = false;
    },

    /* Draws the little map of the saved pin, and returns whether there was
     * anything to draw - the caller shows the plain "View" link when there
     * wasn't, so a location we cannot picture is still reachable.
     *
     * The coordinates are re-parsed here rather than used as they arrived: they
     * reach this through a JSON response, and a map is not the place to find out
     * something was not a number.
     *
     * Kicked off, not awaited. The map arrives a moment after the rest of the
     * form - which is the right order, since the line of text beside it already
     * says what it is going to show. */
    renderLocationPreview(saved, mapUrl) {
        const box = document.getElementById('quoteInfoMap');
        if (!box) return false;

        const lat = parseFloat(saved.latitude);
        const lng = parseFloat(saved.longitude);
        if (!isFinite(lat) || !isFinite(lng)) {
            box.hidden = true;
            return false;
        }

        const coords = lat.toFixed(6) + ',' + lng.toFixed(6);
        // Prefers the customer's own pasted link over the synthesized one, exactly
        // like location_link() in maps.py - it may point at a named place rather
        // than at bare coordinates.
        document.getElementById('quoteInfoMapOpen').href =
            mapUrl || ('https://www.google.com/maps?q=' + coords);
        box.hidden = false;

        this._ensureLocationPicker()
            .then(() => {
                // A browser holding a location-picker.js from before preview() existed
                // would otherwise throw here. It should not happen now the URL is
                // fingerprinted, but "no map" has to stay a handled outcome, not an
                // exception - see the fallback below for why.
                if (!window.EBLocationPicker || typeof EBLocationPicker.preview !== 'function') return null;
                return EBLocationPicker.preview(document.getElementById('quoteInfoMapCanvas'), lat, lng);
            })
            // .catch as well as the null check: EVERY way this can fail has to end at
            // the same place. An unhandled rejection here leaves the box on screen
            // with nothing in it and the "View" link hidden, which is worse than
            // never having shown a map at all.
            .catch(() => null)
            .then(map => {
                // No map - Leaflet unreachable is the realistic case, an office with no
                // route to the tile server. Drop the empty box and put the link back
                // rather than leaving a grey rectangle where a map should be.
                if (map) return;
                box.hidden = true;
                const view = document.getElementById('quoteInfoLocationView');
                if (view && this.savedLocation && this.savedLocation.map_url) view.hidden = false;
            });
        return true;
    },

    /* Leaflet sizes itself from its container, so a map drawn while Order Details
     * was collapsed is zero-height once it is opened again. Re-running preview()
     * re-measures it; it is cheap, and a no-op when there is no pin. */
    refreshLocationPreview() {
        const canvas = document.getElementById('quoteInfoMapCanvas');
        const saved = this.savedLocation;
        if (!canvas || !saved || !window.EBLocationPicker) return;
        EBLocationPicker.preview(canvas, saved.latitude, saved.longitude);
    },

    // ---- changing that pin, without leaving the cart ----
    // The pin belongs to the account, so this really does edit the profile - it just
    // does it here rather than sending a customer with a full cart off to
    // /profile/edit. Same picker either way (partials/location_picker.html).

    /* location-picker.js is not in the app.js bundle: most visits never open the
     * picker, and the ones that do can afford one more request. Loaded like
     * _ensurePdfLibs() loads jsPDF, with one difference that matters - the URL comes
     * from LOCATION_PICKER_URL (base.html), which carries the ?v=<mtime> fingerprint.
     * Static files are cached for 30 days here, so a hand-written path would pin
     * whatever copy a browser fetched first and no later edit would ever reach it.
     *
     * The script registers every .loc-picker on the page as it runs, so by the time
     * this resolves ours is live. */
    _locationPickerPromise: null,
    _ensureLocationPicker() {
        if (window.EBLocationPicker) return Promise.resolve(true);
        if (typeof LOCATION_PICKER_URL === 'undefined') {
            return Promise.reject(new Error('No map picker on this page'));
        }
        if (!this._locationPickerPromise) {
            this._locationPickerPromise = new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = LOCATION_PICKER_URL;
                script.onload = resolve;
                script.onerror = () => reject(new Error('Failed to load the map picker'));
                document.head.appendChild(script);
            }).then(() => true).catch(err => {
                this._locationPickerPromise = null;   // let a later attempt retry
                throw err;
            });
        }
        return this._locationPickerPromise;
    },

    openLocationModal() {
        const overlay = document.getElementById('cartLocationOverlay');
        if (!overlay) return;
        overlay.hidden = false;

        // The prefill request may still be in flight the first time the cart is
        // opened, so wait on it - opening the picker on an empty map when the
        // customer has a pin saved would look like their pin was lost.
        this.ensurePrefill()
            .then(() => this._ensureLocationPicker())
            .then(() => {
                const saved = this.savedLocation || {};
                EBLocationPicker.setValue(
                    'cartLocationPicker', saved.latitude, saved.longitude, saved.map_link
                );
                // Leaflet measures its container at creation time, so a map built
                // while the modal was hidden is zero-height. reveal() builds it now
                // and re-measures one that already exists.
                EBLocationPicker.reveal('cartLocationPicker');
            })
            .catch(() => {
                showToast('The map could not be loaded. Please try again.');
                this.closeLocationModal();
            });
    },

    closeLocationModal() {
        const overlay = document.getElementById('cartLocationOverlay');
        if (overlay) overlay.hidden = true;
    },

    /* Writes the pin to the customer's own record (POST /quote/location), not into
     * the cart: submit() reads it back off that record server-side, so there is
     * nothing here for the order payload to carry. */
    saveLocation() {
        const button = document.getElementById('cartLocationSave');
        const root = document.getElementById('cartLocationPicker');
        if (!button || !root) return;

        const read = name => {
            const input = root.querySelector('[data-loc="' + name + '"]');
            return input ? input.value : '';
        };

        button.disabled = true;
        button.textContent = 'Saving…';
        fetch('/quote/location', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                latitude: read('latitude'),
                longitude: read('longitude'),
                map_link: read('map_link'),
            }),
        })
            // .catch(() => ({})) on the parse: a session that expired mid-cart answers
            // with the sign-in page, not JSON, and an unhandled parse error would put
            // "Unexpected token '<'" in front of the customer instead of something
            // they can act on.
            .then(response => response.json().catch(() => ({})).then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) throw new Error(data.detail || 'Could not save that location.');
                // Redrawn from the server's answer rather than from what was typed,
                // so the line under the address box says what was actually stored.
                this.rememberLocation(data);
                this.closeLocationModal();
                showToast(data.map_url ? 'Delivery location updated.' : 'Delivery location cleared.');
            })
            .catch(err => showToast(err.message || 'Could not save that location.'))
            .finally(() => {
                button.disabled = false;
                button.textContent = 'Save location';
            });
    },

    renderInfoForm() {
        const info = this.getInfo();
        const setVal = (id, key) => {
            const el = document.getElementById(id);
            if (el) el.value = info[key] || '';
        };
        setVal('qiClinic', 'clinic');
        setVal('qiTel', 'tel');
        setVal('qiAddress', 'address');
        setVal('qiPaymentTerm', 'paymentTerm');
        setVal('qiInstallTerm', 'installTerm');
        setVal('qiContactPerson', 'contactPerson');
        setVal('qiPaymentMethod', 'paymentMethod'); // customers only - absent for staff
        // Not setVal(): an unset choice is 'quote', not '', and this <select> has no
        // empty option to fall into - it would render blank instead of on its default.
        const staffDoc = document.getElementById('qiStaffDocument');  // staff only
        if (staffDoc) staffDoc.value = this.staffDocument();
        this.syncStaffDocumentLabel();
    },

    // What a staff cart is set to produce: a plain Quotation (the default and the only
    // thing it could produce before), a Quotation plus a KHQR for the customer to scan,
    // or an Invoice for money already taken. Read in confirmPurchase().
    staffDocument() {
        const canTakePayment = typeof CAN_TAKE_PAYMENT !== 'undefined' && CAN_TAKE_PAYMENT;
        if (!canTakePayment) return 'quote';
        const choice = this.getInfo().staffDocument;
        return (choice === 'khqr' || choice === 'invoice') ? choice : 'quote';
    },

    // The confirm button says what it is about to do, so the choice above isn't
    // something staff have to remember they made. main.js re-reads the label out of
    // data-label whenever it re-enables the button, so both have to be set.
    STAFF_DOCUMENT_LABELS: {
        quote: '<i class="fas fa-file-invoice"></i> Generate Quote',
        khqr: '<i class="fas fa-qrcode"></i> Generate Payment QR',
        invoice: '<i class="fas fa-file-invoice-dollar"></i> Create Invoice',
    },

    syncStaffDocumentLabel() {
        const select = document.getElementById('qiStaffDocument');
        const btn = document.getElementById('quoteDownloadPdfBtn');
        if (!select || !btn) return;
        const label = this.STAFF_DOCUMENT_LABELS[this.staffDocument()];
        if (!label) return;
        btn.dataset.label = label;
        // Not while a submission is in flight - that would wipe the "Saving quote..."
        // spinner the button is currently showing.
        if (!btn.disabled) btn.innerHTML = label;
    },

    // ---- drawer open/close ----
    open() {
        document.getElementById('quoteDrawer')?.classList.add('active');
        document.getElementById('quoteDrawerOverlay')?.classList.add('active');
        // After the drawer is on screen, not before: the fill is a convenience and
        // must never be something the customer waits on to see their cart.
        this.ensurePrefill();
    },

    close() {
        document.getElementById('quoteDrawer')?.classList.remove('active');
        document.getElementById('quoteDrawerOverlay')?.classList.remove('active');
    },

    // ---- render item rows (called on open / add / remove — full rebuild) ----
    // Every server-supplied string below goes through ebEscapeHtml(): these rows are
    // built as an HTML string and assigned to innerHTML, so a product/promotion name
    // containing markup would otherwise be parsed as markup.
    render() {
        this.renderInfoForm();
        this.updateSummary();

        const discountTypeSelect = document.getElementById('quoteDiscountType');
        if (discountTypeSelect) discountTypeSelect.value = this.getDiscountType();
        const discountValueInput = document.getElementById('quoteDiscountValue');
        if (discountValueInput) discountValueInput.value = this.getDiscountValue();

        const items = this.getItems();
        // An empty cart has nothing to quote, so the drawer shows only the empty
        // message: .is-empty hides the Quote Info form above it and the totals /
        // Confirm Purchase footer below (see base.css). Those were asking for clinic
        // details and offering to submit an order with no lines in it -
        // confirmPurchase() already refuses that, so the button was never live.
        document.getElementById('quoteDrawer')?.classList.toggle('is-empty', items.length === 0);

        const itemsEl = document.getElementById('quoteDrawerItems');
        if (!itemsEl) return;

        if (items.length === 0) {
            itemsEl.innerHTML = `
                <div class="quote-drawer-empty">
                    <i class="fas fa-shopping-cart"></i>
                    <p>Your cart is empty.<br>Add products to get started.</p>
                </div>`;
            return;
        }

        itemsEl.innerHTML = items.map(item => `
            <div class="quote-item" data-id="${item.id}" data-kind="${ebEscapeHtml(item.kind)}">
                <img src="${ebEscapeHtml(item.image || 'https://images.unsplash.com/photo-1587825140708-dfaf72ae4b04?w=100&h=100&fit=crop&auto=format')}" alt="${ebEscapeHtml(item.name)}">
                <div class="quote-item-info">
                    <div class="quote-item-name">${ebEscapeHtml(item.name)}</div>
                    <div class="quote-item-fixed-meta">
                        <span>${ebEscapeHtml(item.code || (item.kind === 'promotion' ? 'Promo' : item.kind === 'set' ? 'Set' : '—'))}</span>
                        <span>${ebEscapeHtml(item.uom || (item.kind === 'product' ? 'PCS' : ''))}</span>
                        <span>$${item.price.toFixed(2)} ea</span>
                        <span>${formatItemDiscount(item.discount, item.discountType) || 'No discount'}</span>
                    </div>
                    <div class="quote-item-row-footer">
                        <div class="quote-item-controls">
                            <button type="button" class="quote-qty-btn" onclick="QuoteCart.changeQty(${item.id}, -1, '${item.kind}', '${ebEscapeHtml(item.optKey || '')}')"><i class="fas fa-minus"></i></button>
                            <span class="quote-qty-value">${item.qty}</span>
                            <button type="button" class="quote-qty-btn" onclick="QuoteCart.changeQty(${item.id}, 1, '${item.kind}', '${ebEscapeHtml(item.optKey || '')}')"><i class="fas fa-plus"></i></button>
                        </div>
                        <span class="quote-item-amount">$${this.lineAmount(item).toFixed(2)}</span>
                        <button type="button" class="quote-item-remove" onclick="QuoteCart.removeItem(${item.id}, '${item.kind}', '${ebEscapeHtml(item.optKey || '')}')"><i class="fas fa-trash"></i></button>
                    </div>
                    ${this.renderIncluded(item)}
                </div>
            </div>`).join('');
    },

    // What the line includes at no charge: a promotion/set's member products, or
    // a product's free gifts. Read-only - they have no price and no quantity of
    // their own, they just follow the parent line (see changeQty).
    renderIncluded(item) {
        if (!item.components || item.components.length === 0) return '';
        return `
            <ul class="quote-item-included">
                ${item.components.map(component => `
                    <li>
                        <span class="included-name">+ ${ebEscapeHtml(component.name)}</span>
                        <span class="included-qty" data-unit-qty="${component.qty}">×${component.qty * item.qty}</span>
                        <span class="included-price">—</span>
                    </li>`).join('')}
            </ul>`;
    },

    // ---- print template + PDF export ----
    // Split into two reusable pieces so an already-placed order can be re-printed later
    // (see the admin Orders page's Print button) without resubmitting anything:
    //   buildPrintTemplate(order) - pure: fills #quotePrintTemplate purely from a server
    //     Order object (quote_code/clinic_name/.../items/discount_amount/grand_total) -
    //     never from local cart/info state, so a reprint always matches what's actually
    //     on record.
    //   exportPDF(filenameSuffix) - snapshots the already-filled template with
    //     html2canvas (needed for Khmer glyphs, which jsPDF's built-in fonts can't draw)
    //     and saves it as a PDF, sliced across pages if taller than one A4 page.
    _formatQuoteDate(iso) {
        const d = iso ? new Date(iso) : new Date();
        return String(d.getDate()).padStart(2, '0') + '/' + String(d.getMonth() + 1).padStart(2, '0') + '/' + d.getFullYear();
    },

    // NOTE: this builds an HTML string and assigns it to innerHTML, and most of
    // the `order` fields it interpolates are free text the CUSTOMER typed into the
    // checkout form (clinic_name, address, contact_person, phone, terms). They all
    // go through ebEscapeHtml() - without it, a customer could place an order whose
    // clinic name is markup, and it would execute in a staff member's session the
    // moment they hit Print on the admin Orders page.
    buildPrintTemplate(order) {
        // Three outcomes, in this order - the mirror of document_title() in store-api's
        // services/invoice_pdf.py, which must agree with this line for line:
        //   1. A CANCELLED order is never an invoice, paid or not. It prints as
        //      "Cancelled Order": a cancelled sale that had been paid is money owed
        //      back, and a page headed "Invoice" claims that sale still stands.
        //   2. Anything with a payment on record is an Invoice - a confirmed KHQR
        //      payment, or a quote staff marked paid after taking cash at the counter.
        //      Keyed on payment_status, NOT payment_method/order_type: a paid quote IS
        //      the sale, and the document the customer keeps should say so.
        //   3. Everything else stays a Quotation.
        //
        // A REFUNDED row is an Invoice under (2): that invoice was genuinely issued and
        // is what the refund was made against, so re-titling it a Quotation would deny
        // it ever existed. What changes is the terms box, which says it was refunded
        // and drops the pay-me QR (see termsLines below, and REFUNDED_NOTE in
        // invoice_pdf.py, which must keep saying the same thing).
        //
        // (2) said "Receipt" until 2026-08-17; renamed to Invoice throughout on the
        // owner's instruction. The `receipt_note_*` setting keys kept their names.
        const isCancelled = order.status === 'cancelled';
        const isPaidDocument = order.payment_status === 'paid' && !isCancelled;
        const isRefunded = order.payment_status === 'refunded' && !isCancelled;
        const docTitle = isCancelled
            ? 'Cancelled Order'
            : ((isPaidDocument || isRefunded) ? 'Invoice' : 'Quotation');
        // Letterhead and wording are admin-editable (Settings -> Quote & Invoice),
        // delivered as EB_SETTINGS by base.html / _admin_base.html. The fallbacks below
        // are only reached if that blob is missing entirely - store-api's spec holds the
        // real defaults, and its own PDF builder (services/invoice_pdf.py) reads the
        // same keys. Changing wording here means changing it there too.
        const cfg = (typeof EB_SETTINGS !== 'undefined' && EB_SETTINGS) || {};
        // The terms box at the foot of the item table. A quotation carries the shop's
        // standing terms and the bank QR to pay against; a paid invoice and a cancelled
        // order each carry a single line saying so, and no QR - "please scan to pay" on
        // a document that is already settled, or void, reads as a mistake. Mirrored by
        // the terms_lines block in build_invoice_pdf() in store-api's
        // services/invoice_pdf.py.
        //
        // The cancelled line is a literal in both engines (CANCELLED_NOTE there): it
        // states a fact about the row rather than wording the shop picks. The settings-
        // driven lines are escaped - they are typed by an admin rather than by a
        // customer, so this is belt and braces rather than the load-bearing escaping
        // the `order` fields get, but a settings screen is not a place to author markup.
        const termsLines = (isCancelled
            ? ['This order was cancelled. It is not an invoice and is not payable.']
            : isRefunded
            ? [
                'This invoice has been refunded. The payment was returned to the customer.'
                    + (order.refunded_at ? ` (${ebEscapeHtml(QuoteCart._formatQuoteDate(order.refunded_at))})` : ''),
                order.refund_reason ? `Reason: ${ebEscapeHtml(order.refund_reason)}` : '',
            ]
            : isPaidDocument
            ? [ebEscapeHtml(order.payment_method === 'khqr'
                ? (cfg.receipt_note_khqr || 'Paid via KHQR. Thank you for your purchase.')
                : (cfg.receipt_note_cash || 'Paid in full. Thank you for your purchase.'))]
            : [
                `Quotation is valid for <b>${Number(cfg.quote_validity_days) || 30} days</b> from the date issued.`,
                ebEscapeHtml(cfg.quote_deposit_note || ''),
                ebEscapeHtml(cfg.quote_payment_note || ''),
            ]).filter(Boolean);

        // The payment QR is served by THIS app (/quote-payment-qr.png in
        // blueprints/main.py) rather than from the URL the setting actually holds: the
        // picture lives on store-api or on R2, and html2canvas cannot export a canvas
        // that has drawn a cross-origin image. `?v=` is the stored filename (a uuid),
        // so replacing the picture in Settings busts the browser's copy of the old one.
        const storedQr = isCancelled || isPaidDocument || isRefunded ? '' : (cfg.quote_payment_qr || '').trim();
        const qrCaption = ebEscapeHtml(cfg.quote_payment_qr_caption || '');
        const termsQr = storedQr ? `
                    <div class="qpt-terms-qr">
                        <img src="/quote-payment-qr.png?v=${encodeURIComponent(storedQr.split('/').pop())}" alt="Payment QR code">
                        ${qrCaption ? `<div class="qpt-terms-qr-caption">${qrCaption}</div>` : ''}
                    </div>` : '';

        const specialDiscountLabel = order.discount_type === 'cash'
            ? 'Special Discount (Cash):'
            : `Special Discount (${Number(order.discount_value || 0)}%):`;

        // "UP before & After Discount" — UP is the ORIGINAL price (unit_price
        // reconstructed from the charged item.unit_price + its snapshotted
        // discount, same reconstruction as deriveOldUnitPrice/derive_old_price),
        // Discount is the %, and Amount (line_amount) is the price actually
        // charged × qty.
        const undiscountedSubtotal = order.items.reduce(
            (sum, item) => sum + deriveOldUnitPrice(item) * item.qty, 0
        );
        const itemDiscountTotal = printedCashDiscountTotal(order.items);

        // Component lines (a promotion/set's contents, a product's free gifts -
        // OrderItem.parent_item_id in store-api) come back in the same flat list,
        // ordered right after the line they belong to. They print as $0.00
        // "Free" sub-rows, but they DO take a No. of their own (owner's call,
        // 2026-08-20): whoever receives the document counts and ticks off every
        // physical item on it, and a numbered set followed by eight blank-numbered
        // rows read as gaps. So the No. is simply the row's position - one run
        // across paid lines and free ones alike, which is why this is an index
        // rather than a counter that skips. Mirrored by store-api's fallback PDF
        // (services/invoice_pdf.py).
        const rows = order.items.map((item, index) => {
            const lineNo = index + 1;
            if (item.parent_item_id) {
                return `
            <tr class="qpt-component-row">
                <td class="qpt-num">${lineNo}</td>
                <td>${ebEscapeHtml(item.product_code || '—')}</td>
                <td class="qpt-component-name">• ${ebEscapeHtml(item.product_name)}</td>
                <td class="qpt-num">${item.qty}</td>
                <td class="qpt-num">${ebEscapeHtml(item.uom || 'PCS')}</td>
                <td class="qpt-right">$ 0.00</td>
                <td class="qpt-num">—</td>
                <td class="qpt-right">$ 0.00</td>
            </tr>`;
            }
            return `
            <tr>
                <td class="qpt-num">${lineNo}</td>
                <td>${ebEscapeHtml(item.product_code || '—')}</td>
                <td>${ebEscapeHtml(item.product_name)}</td>
                <td class="qpt-num">${item.qty}</td>
                <td class="qpt-num">${ebEscapeHtml(item.uom || 'PCS')}</td>
                <td class="qpt-right">$ ${deriveOldUnitPrice(item).toFixed(2)}</td>
                <td class="qpt-num">${printedItemDiscountText(item) || '—'}</td>
                <td class="qpt-right">$ ${printedItemAmount(item).toFixed(2)}</td>
            </tr>`;
        }).join('');

        // Pad the table with blank rows so it always looks like a full,
        // pre-printed form (like the paper original) even when there are
        // only a few items on the quote.
        const MIN_TABLE_ROWS = 21;
        const blankRowsNeeded = Math.max(0, MIN_TABLE_ROWS - order.items.length);
        const blankRows = Array.from({ length: blankRowsNeeded }).map(() => `
            <tr class="qpt-blank-row">
                <td>&nbsp;</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>`).join('');

        const template = document.getElementById('quotePrintTemplate');
        template.innerHTML = `
            <div class="qpt-header">
                <div>
                    <div class="qpt-brand-name">${ebEscapeHtml(cfg.document_brand_name || 'EB DENTAL')}</div>
                    <div class="qpt-brand-meta">
                        ${ebEscapeHtml(cfg.document_address_line || 'Phnom Penh, Cambodia')}
                        ${cfg.document_tel_line ? `<br>Tel: ${ebEscapeHtml(cfg.document_tel_line)}` : ''}
                    </div>
                </div>
                <div>
                    <div class="qpt-title">${docTitle}</div>
                    <div class="qpt-meta-right">
                        No : <b>${ebEscapeHtml(order.order_number)}</b><br>
                        Date: <b>${this._formatQuoteDate(order.created_at)}</b>
                    </div>
                </div>
            </div>

            <div class="qpt-info-block">
                <div class="qpt-info-col">
                    <div class="qpt-info-row"><span class="qpt-info-label">C. Code</span><span class="qpt-info-value">${ebEscapeHtml(order.quote_code || '—')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Clinic</span><span class="qpt-info-value qpt-khmer">${ebEscapeHtml(order.clinic_name || '—')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Contact Tel</span><span class="qpt-info-value">${ebEscapeHtml(order.phone || '—')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Address</span><span class="qpt-info-value qpt-khmer">${ebEscapeHtml(order.address || '—')}</span></div>
                </div>
                <div class="qpt-info-col">
                    <div class="qpt-info-row"><span class="qpt-info-label">Payment Term</span><span class="qpt-info-value">${ebEscapeHtml(order.payment_term || 'COD')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Salesperson</span><span class="qpt-info-value">${ebEscapeHtml(order.salesperson || '—')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">User</span><span class="qpt-info-value">${ebEscapeHtml(order.quoted_by_name || '—')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Installation Term</span><span class="qpt-info-value">${ebEscapeHtml(order.install_term || 'Free within Phnom Penh')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Contact Person</span><span class="qpt-info-value">${ebEscapeHtml(order.contact_person || cfg.default_contact_person || '—')}</span></div>
                </div>
            </div>

            <table class="qpt-table">
                <thead>
                    <!-- One header row, not two. There used to be a second, empty
                         <th></th><th></th> row under the colspan header, there only to
                         fill out the grid - and .qpt-table borders every cell, so it
                         printed as a boxed sliver with a divider down the middle: stray
                         lines inside the "UP before & After Discount" cell on every
                         document. Removed on the owner's instruction; store-api's fpdf2
                         builder (invoice_pdf.py) drops the same row so the two agree. -->
                    <tr>
                        <th>No.</th>
                        <th>Code</th>
                        <th>Description</th>
                        <th>Qty</th>
                        <th>UOM</th>
                        <th colspan="2">UP before &amp; After Discount</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                    ${blankRows}
                    <tr class="qpt-total-row qpt-subtotal-row">
                        <td colspan="6" class="qpt-validity" rowspan="4">
                            <div class="qpt-terms">
                                <div class="qpt-terms-text">${termsLines.map(line => `<div>${line}</div>`).join('')}</div>
                                ${termsQr}
                            </div>
                        </td>
                        <td>Sub-Total($):</td>
                        <td class="qpt-right">$ ${undiscountedSubtotal.toFixed(2)}</td>
                    </tr>
                    <tr class="qpt-total-row">
                        <td>Discount($):</td>
                        <td class="qpt-right">$ ${itemDiscountTotal.toFixed(2)}</td>
                    </tr>
                    <tr class="qpt-total-row">
                        <td>${specialDiscountLabel}</td>
                        <td class="qpt-right">$ ${Number(order.discount_amount).toFixed(2)}</td>
                    </tr>
                    <tr class="qpt-total-row qpt-grand-total-row">
                        <td>Grand Total:</td>
                        <td class="qpt-right">$ ${Number(order.grand_total).toFixed(2)}</td>
                    </tr>
                </tbody>
            </table>

            <div class="qpt-sign-strip">
                <div class="qpt-sign-col"><div class="qpt-sign-line qpt-khmer">ទទួលប្រាក់ដោយ<br>Cash received by</div></div>
                <div class="qpt-sign-col"><div class="qpt-sign-line qpt-khmer">ទទួលដោយ<br>Received by</div></div>
                <div class="qpt-sign-col"><div class="qpt-sign-line qpt-khmer">ដឹកដោយ<br>Delivered by</div></div>
                <div class="qpt-sign-col"><div class="qpt-sign-line qpt-khmer">បញ្ជូនដោយ<br>Issued by</div></div>
                <div class="qpt-sign-col"><div class="qpt-sign-line qpt-khmer">រៀបចំដោយ<br>Prepared by</div></div>
            </div>
        `;
    },

    // jsPDF + html2canvas are deliberately NOT in base.html anymore - they're only
    // needed for PDF export, so they're injected here on first use. The promise is
    // cached so repeated exports load them once; on failure it's cleared so a retry
    // can attempt the download again.
    //
    // Served from /static/vendor/ rather than cdnjs (see scripts/vendor_assets.py):
    // still lazy, but "export this quote as a PDF" now works on a box with no route
    // to the internet, which is the normal state of the office this runs in.
    _pdfLibsPromise: null,
    _ensurePdfLibs() {
        if (window.jspdf && window.html2canvas) return Promise.resolve();
        if (!this._pdfLibsPromise) {
            const urls = [
                '/static/vendor/jspdf.umd.min.js',
                '/static/vendor/html2canvas.min.js',
            ];
            this._pdfLibsPromise = Promise.all(urls.map(src => new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = src;
                script.onload = resolve;
                script.onerror = () => reject(new Error('Failed to load ' + src));
                document.head.appendChild(script);
            }))).catch(err => {
                this._pdfLibsPromise = null;
                throw err;
            });
        }
        return this._pdfLibsPromise;
    },

    // Returns the built PDF as a Blob (in addition to triggering the local download)
    // so confirmPurchase() can also hand it to store-api for the Telegram order alert
    // - see uploadQuotationPDF(). The admin reprint button (admin/orders.html) calls
    // this too and just ignores the return value. `docName` is the filename word only
    // ("Quotation"/"Invoice") - the printed title inside the document comes from
    // buildPrintTemplate(), which must already have been called.
    async exportPDF(filenameSuffix, docName = 'Quotation') {
        await this._ensurePdfLibs();
        const template = document.getElementById('quotePrintTemplate');

        // Give web fonts a beat to be ready before the snapshot.
        if (document.fonts && document.fonts.ready) await document.fonts.ready;

        const canvas = await html2canvas(template, { scale: 2, backgroundColor: '#ffffff', useCORS: true });
        const imgData = canvas.toDataURL('image/png');

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF({ unit: 'pt', format: 'a4' });
        const pdfWidth = pdf.internal.pageSize.getWidth();
        const pdfHeight = pdf.internal.pageSize.getHeight();
        const imgWidth = pdfWidth;
        const imgHeight = (canvas.height * imgWidth) / canvas.width;

        // How many A4 pages this snapshot actually needs.
        //
        // The template is built to A4's own proportions, so a one-page quotation
        // lands a hair OVER a page once scaled to points - 843pt of image against
        // an 841.89pt page, from border rounding and the fractional row heights
        // html2canvas reports. The previous loop paged on any overflow at all,
        // which is why every quote came out as two pages with a hairline sliver on
        // the second (owner's report, 2026-08-20).
        //
        // SINGLE_PAGE_SLACK is the margin of overflow treated as "still one page".
        // Whatever page count that yields, the image is then scaled to fill exactly
        // that many pages, so the fit is absorbed by an imperceptible shrink instead
        // of by spilling - and NOTHING is dropped, which is why this scales rather
        // than simply ignoring a small remainder. A genuinely longer quote (more
        // items than the form's 21 rows) still slices across real pages.
        const SINGLE_PAGE_SLACK = 1.05;
        const pageCount = Math.max(1, Math.ceil(imgHeight / (pdfHeight * SINGLE_PAGE_SLACK)));
        const fit = Math.min(1, (pageCount * pdfHeight) / imgHeight);
        const drawWidth = imgWidth * fit;
        const drawHeight = imgHeight * fit;
        // Centred, so the sliver of width given up by that shrink shows as an even
        // margin on both sides rather than a lopsided one on the right.
        const drawX = (pdfWidth - drawWidth) / 2;

        for (let page = 0; page < pageCount; page++) {
            if (page > 0) pdf.addPage();
            // The whole image is placed on every page, shifted up by the pages
            // already drawn; jsPDF clips it to the page box.
            pdf.addImage(imgData, 'PNG', drawX, -page * pdfHeight, drawWidth, drawHeight);
        }

        pdf.save('EB-Dental-' + docName + '-' + filenameSuffix + '.pdf');
        return pdf.output('blob');
    },

    // Best-effort hand-off of the real client-rendered PDF to store-api, which uses it
    // for the order's Telegram alert instead of its own fpdf2 approximation - see
    // deliver_order_alert/resolve_pending_quotation_pdf in store-api's
    // services/telegram.py. Deliberately fire-and-forget (never awaited by the caller,
    // errors swallowed): store-api only waits ~20s for this before falling back on its
    // own, so a slow/failed upload here just means that fallback gets used - it must
    // never block or fail the purchase flow the customer is already looking at.
    uploadQuotationPDF(orderId, pdfBlob) {
        const formData = new FormData();
        formData.append('file', pdfBlob, 'quotation.pdf');
        fetch(`/quote/${orderId}/pdf`, { method: 'POST', body: formData }).catch(() => {});
    },

    // "Confirm Purchase" / "Generate Quote" submits the cart to POST /quote/submit -
    // this creates a real store-api Order (server re-prices every line, derives
    // salesperson/quoted_by_name, and computes the discount itself - never trusting
    // what the browser sends, see routers/orders.py). What happens next depends on
    // who's confirming:
    //   staff            -> the row is a QUOTE; quotation PDF downloads immediately.
    //   customer + cash  -> also a QUOTE (payment happens offline later); same PDF flow.
    //   customer + khqr  -> a real order awaiting payment; the KHQR modal opens and the
    //                       RECEIPT is only generated once the payment-status poll
    //                       reports "paid" - see showKhqrModal()/_finishPaidOrder().
    async confirmPurchase() {
        const items = this.getItems();
        if (items.length === 0) return;

        const info = this.getInfo();
        if (!info.clinic || !info.tel || !info.address) {
            // Expand the (possibly collapsed) info form first, so the fields
            // being complained about are already on screen behind the dialog.
            document.getElementById('quoteInfoForm')?.classList.remove('collapsed');
            await ebAlert('Please fill in Clinic, Contact Tel, and Address before confirming your purchase.', {
                title: 'Missing details',
                tone: 'warning',
                confirmText: 'Got it',
            });
            return;
        }

        // Customers must pick how they'll pay; staff never see the selector (their
        // cart always produces a quote). store-api enforces the same rule server-side.
        const isStaff = typeof IS_STAFF !== 'undefined' && IS_STAFF;
        const paymentMethod = isStaff ? null : (info.paymentMethod || '');
        if (!isStaff && paymentMethod !== 'cash' && paymentMethod !== 'khqr') {
            document.getElementById('quoteInfoForm')?.classList.remove('collapsed');
            await ebAlert('Please choose a payment method (Cash or KHQR) before confirming your purchase.', {
                title: 'Payment method required',
                tone: 'warning',
                confirmText: 'Got it',
            });
            return;
        }

        const btn = document.getElementById('quoteDownloadPdfBtn');
        const btnLabel = (btn && btn.dataset.label) || '<i class="fas fa-circle-check"></i> Confirm Purchase';
        const resetBtn = () => {
            if (btn) { btn.disabled = false; btn.innerHTML = btnLabel; }
        };
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + (isStaff ? 'Saving quote...' : 'Submitting order...');
        }

        let order;
        try {
            const response = await fetch(QUOTE_SUBMIT_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clinic_name: info.clinic,
                    contact_person: info.contactPerson || null,
                    phone: info.tel,
                    address: info.address,
                    payment_term: info.paymentTerm || null,
                    install_term: info.installTerm || null,
                    payment_method: paymentMethod || null,
                    discount_type: this.getDiscountType(),
                    discount_value: this.getDiscountValue(),
                    // `options` rides along on a configured set line so store-api can
                    // re-price the upgrades; it is [] for every other kind of line.
                    items: items.map(item => ({
                        id: item.id, qty: item.qty, kind: item.kind,
                        options: item.options || [],
                    })),
                }),
            });
            order = await response.json();
            if (!response.ok) {
                resetBtn();
                await ebAlert(order.detail || 'Could not submit your quote. Please try again.', {
                    title: isStaff ? "Couldn't save your quote" : "Couldn't submit your order",
                    tone: 'danger',
                });
                return;
            }
        } catch (err) {
            resetBtn();
            await ebAlert('Could not reach the server. Please check your connection and try again.', {
                title: 'Connection problem',
                tone: 'danger',
            });
            return;
        }
        // Deliberately not a `finally` on the block above: bailing out on an
        // error there used to fall through it and leave the button stuck
        // disabled on "Generating PDF..." forever, since the reset only lived
        // on the success path's own finally below.

        // KHQR: NO order exists yet, and none will until the payment is confirmed -
        // store-api returns a checkout (the QR to render and an id to poll) instead.
        // The order, and with it the invoice, comes into existence in _finishPaidOrder.
        if (order.checkout) {
            resetBtn();
            this.clearDraft();
            this.render();
            this.close();
            this.showKhqrModal(order.checkout);
            return;
        }

        // Staff only, and only for the two non-default choices: the row store-api just
        // wrote is a quote either way, and this is what happens to it next. Both steps
        // are best-effort on purpose - the quote EXISTS by now, so a QR that couldn't be
        // issued or a payment that couldn't be recorded must not swallow it. Either
        // failure says so and falls through to the ordinary quotation document, which
        // staff can then finish from the admin Orders page.
        const staffDocument = isStaff ? this.staffDocument() : 'quote';
        if (staffDocument === 'invoice') {
            if (btn) { btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Recording payment...'; }
            const paid = await this._staffOrderAction(
                ORDER_INVOICE_URL_TEMPLATE, order.id, "Couldn't record the payment"
            );
            if (paid) order = paid;
        } else if (staffDocument === 'khqr') {
            if (btn) { btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Issuing the QR...'; }
            const withQr = await this._staffOrderAction(
                ORDER_KHQR_URL_TEMPLATE, order.id, "Couldn't issue a payment QR"
            );
            if (withQr && withQr.khqr_string) order = withQr;
        }

        if (btn) { btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating PDF...'; }

        try {
            this.buildPrintTemplate(order);
            // Whichever document the order actually became. "Invoice" is keyed on the
            // payment flag store-api came back with, never on what was asked for, so a
            // refused payment can't produce a file named Invoice.
            const isPaidNow = order.payment_status === 'paid';
            const pdfBlob = await this.exportPDF(order.quote_code, isPaidNow ? 'Invoice' : 'Quotation');
            this.uploadQuotationPDF(order.id, pdfBlob);
            this.clearDraft();
            this.render();
            this.close();
        } finally {
            resetBtn();
        }

        // Last, so the cart is already emptied and shut behind it: the QR stays on
        // screen until staff close it, and it polls for the payment while it's there.
        if (order.khqr_string && staffDocument === 'khqr') {
            await this.showOrderQrModal(order);
        }
    },

    // POSTs one of the staff-only order actions in blueprints/quote.py (issue a KHQR /
    // record the order as paid) and returns the updated order, or null after telling
    // the user why not. Callers treat null as "carry on with the plain quote".
    async _staffOrderAction(urlTemplate, orderId, failureTitle) {
        try {
            const resp = await fetch(urlTemplate.replace('/0/', '/' + orderId + '/'), {
                method: 'POST',
                headers: { 'Accept': 'application/json' },
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || 'Please try again from the Orders page.');
            return data;
        } catch (err) {
            await ebAlert(
                (err && err.message ? err.message : 'Please try again from the Orders page.')
                + ' The quote itself has been saved.',
                { title: failureTitle, tone: 'danger' }
            );
            return null;
        }
    },

    // ---- KHQR payment (customer QR checkout only) ----
    // qrcode.js is lazy-loaded exactly like jsPDF/html2canvas above - only a KHQR
    // checkout ever pays the download cost.
    _qrLibPromise: null,
    _ensureQrLib() {
        if (window.QRCode) return Promise.resolve();
        if (!this._qrLibPromise) {
            this._qrLibPromise = new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = '/static/vendor/qrcode.min.js';
                script.onload = resolve;
                script.onerror = () => reject(new Error('Failed to load qrcode.js'));
                document.head.appendChild(script);
            }).catch(err => {
                this._qrLibPromise = null;
                throw err;
            });
        }
        return this._qrLibPromise;
    },

    _khqrPollTimer: null,
    _stopKhqrPolling() {
        if (this._khqrPollTimer) {
            clearInterval(this._khqrPollTimer);
            this._khqrPollTimer = null;
        }
    },

    // Paints the KHQR card - amount, the code itself, the caption under it, the status
    // line. Shared by the only two things that ever put a QR on screen: a customer
    // paying for their own order (showKhqrModal) and a staff member issuing one against
    // a quote they have just raised (showOrderQrModal), so the two can't drift into
    // presenting the same code differently.
    //
    // `download` is the filename stem for the "Download QR" button, or null to leave
    // that button hidden - it exists so staff can send the code to a customer who isn't
    // standing in front of the screen, which is not something the customer themselves
    // has any use for. Returns false only when the modal isn't on the page at all;
    // a code that couldn't be DRAWN leaves its own message in the box and still returns
    // true, because the payment behind it is live either way and worth polling.
    async _renderKhqrCard({ amount, caption, khqrString, statusHtml, download }) {
        const overlay = document.getElementById('khqrModalOverlay');
        if (!overlay) return false;

        document.getElementById('khqrAmount').textContent = '$' + Number(amount).toFixed(2);
        document.getElementById('khqrOrderNo').textContent = caption;
        document.getElementById('khqrStatusRow').innerHTML = statusHtml;

        const downloadBtn = document.getElementById('khqrDownloadBtn');
        this._qrDownload = download ? { boxId: 'khqrCodeBox', ...download, amount, caption } : null;
        if (downloadBtn) downloadBtn.style.display = download ? '' : 'none';

        const codeBox = document.getElementById('khqrCodeBox');
        codeBox.innerHTML = '';
        // Up before qrcode.js is fetched, not after: on a slow connection that's a
        // second or two of the customer looking at the page they just left.
        overlay.style.display = 'flex';
        try {
            await this._ensureQrLib();
            new QRCode(codeBox, {
                text: khqrString,
                width: 220,
                height: 220,
                correctLevel: QRCode.CorrectLevel.M,
            });
        } catch (err) {
            codeBox.textContent = 'Could not draw the QR code — please check your connection and try again.';
            // Nothing to save if nothing was drawn.
            if (downloadBtn) downloadBtn.style.display = 'none';
            this._qrDownload = null;
        }
        return true;
    },

    // `checkout` is a pending payment, NOT an order: it has an id to poll, the QR to
    // render and the amount owed, and that's all that exists until the money arrives.
    async showKhqrModal(checkout) {
        this._khqrStaffMode = false;
        const shown = await this._renderKhqrCard({
            amount: checkout.grand_total,
            // No order number to show yet - there is no order. The reference is what the
            // payment appears as at the bank, which is the useful thing if anything needs
            // chasing up by hand.
            caption: 'Ref ' + checkout.reference,
            khqrString: checkout.khqr_string,
            statusHtml: '<i class="fas fa-spinner fa-spin"></i> Scan with your banking app — waiting for payment…',
            download: null,
        });
        if (!shown) return;

        // Poll every 3s. Transient failures are ignored (just try again next tick); the
        // loop ends on "paid", on "expired", or when the user closes the modal.
        // Server-side, the first poll that finds the payment is what CREATES the order
        // and fires the Telegram alert - see store-api's
        // routers/orders.py::check_checkout_payment. If the customer closes the tab
        // mid-payment nothing is lost: the server's own sweep does the same job.
        const url = CHECKOUT_STATUS_URL_TEMPLATE.replace('/0/', '/' + checkout.id + '/');
        this._stopKhqrPolling();
        this._khqrPollTimer = setInterval(async () => {
            let data;
            try {
                const resp = await fetch(url);
                if (!resp.ok) return;
                data = await resp.json();
            } catch {
                return;
            }
            if (data.payment_status === 'paid' && data.order) {
                this._stopKhqrPolling();
                await this._finishPaidOrder(data.order);
            } else if (data.payment_status === 'expired') {
                this._stopKhqrPolling();
                this.hideKhqrModal();
                await ebAlert('This payment code has expired before the payment arrived. Nothing has been charged — please add your items again to get a fresh code.', {
                    title: 'Payment code expired',
                    tone: 'danger',
                });
            }
        }, 3000);
    },

    hideKhqrModal() {
        this._stopKhqrPolling();
        this._khqrStaffMode = false;
        this._qrDownload = null;
        const overlay = document.getElementById('khqrModalOverlay');
        if (overlay) overlay.style.display = 'none';
    },

    // ---- staff KHQR (a QR issued against an order that already exists) ----
    // The staff counterpart to showKhqrModal. Nothing here creates anything: the quote
    // was written a moment ago by confirmPurchase() and store-api has already put a
    // KHQR for its exact grand total onto it (POST /quote/<id>/khqr). This shows that
    // code, offers it as an image to send to whoever is paying, and watches for the
    // money - at which point the same order's document prints as an Invoice.
    //
    // Staff can close it at any time and lose nothing: the QR is stored on the order,
    // the admin Orders page re-opens that very same one, and store-api's own sweep
    // records the payment whether or not anybody is watching.
    async showOrderQrModal(order) {
        this._khqrStaffMode = true;
        const shown = await this._renderKhqrCard({
            amount: order.grand_total,
            caption: 'No. ' + (order.order_number || order.quote_code || '')
                + (order.clinic_name ? ' · ' + order.clinic_name : ''),
            khqrString: order.khqr_string,
            statusHtml: '<i class="fas fa-spinner fa-spin"></i> Waiting for the customer to pay…',
            download: { filename: 'EB-Dental-KHQR-' + (order.order_number || order.quote_code || 'order') },
        });
        if (!shown) return;

        // Same 3s loop and the same endpoint the admin Orders page's QR dialog polls -
        // store-api asks Bakong/PayWay, and the first confirmed check is what flips the
        // order to paid and fires the paid-order alert.
        const url = ORDER_PAYMENT_STATUS_URL_TEMPLATE.replace('/0/', '/' + order.id + '/');
        this._stopKhqrPolling();
        this._khqrPollTimer = setInterval(async () => {
            let data;
            try {
                const resp = await fetch(url);
                if (!resp.ok) return;
                data = await resp.json();
            } catch {
                return;
            }
            if (data.payment_status === 'paid') {
                this._stopKhqrPolling();
                await this._finishStaffPaidOrder(order);
            }
        }, 3000);
    },

    // The staff mirror of _finishPaidOrder: a customer has just paid a QR staff issued
    // at the counter, so the document that comes out is the Invoice for that sale.
    async _finishStaffPaidOrder(order) {
        const statusRow = document.getElementById('khqrStatusRow');
        if (statusRow) {
            statusRow.innerHTML = '<i class="fas fa-circle-check" style="color:#16a34a;"></i> Payment received — generating the invoice…';
        }
        // The poll reports one flag, and payment_status is the single field both document
        // builders key on (docTitle in buildPrintTemplate here, document_title() in
        // store-api) - so it is set locally rather than re-fetching the whole order to
        // learn one boolean. Everything else on it is still current.
        const paidOrder = { ...order, payment_status: 'paid' };
        try {
            this.buildPrintTemplate(paidOrder);
            const pdfBlob = await this.exportPDF(paidOrder.quote_code, 'Invoice');
            this.uploadQuotationPDF(paidOrder.id, pdfBlob);
        } catch (err) {
            // The payment is on record server-side either way - a PDF hiccup must never
            // read as a failed payment.
        }
        this.hideKhqrModal();
        await ebAlert('Payment received. The invoice has been downloaded.', {
            title: 'Payment complete',
            tone: 'success',
            confirmText: 'Done',
        });
    },

    // Saves the code on screen as a PNG that still makes sense once it leaves this page:
    // the shop name, the amount and the order number are drawn onto the image, so a
    // customer who receives it in a chat can see what they are about to pay for.
    // Composed on a fresh canvas rather than saving qrcode.js's own, which is 220px of
    // unlabelled squares. Staff only - the button is hidden in the customer flow.
    //
    // `meta` is {boxId, amount, caption, filename}; it defaults to whatever the cart's
    // own KHQR modal last drew, and the admin Orders page passes its own dialog's box in
    // so both "Download QR" buttons produce the identical image.
    downloadQrImage(meta) {
        meta = meta || this._qrDownload;
        const box = meta && document.getElementById(meta.boxId || 'khqrCodeBox');
        // qrcode.js draws a <canvas> and keeps an <img> copy of it for the browsers that
        // can't use one; either is a valid source for drawImage, and that img's src is a
        // data: URL off the same canvas, so neither taints this one.
        const source = box && (box.querySelector('canvas') || box.querySelector('img'));
        if (!meta || !source) return;

        const cfg = (typeof EB_SETTINGS !== 'undefined' && EB_SETTINGS) || {};
        const FONT = '"Segoe UI", Roboto, Helvetica, Arial, sans-serif';
        const W = 560, QR = 360;
        const canvas = document.createElement('canvas');
        canvas.width = W;
        canvas.height = 700;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, W, canvas.height);

        // KHQR's own red band, so the saved image still reads as a KHQR code rather than
        // as a random square somebody pasted into a chat.
        ctx.fillStyle = '#e21836';
        ctx.fillRect(0, 0, W, 84);
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 32px ' + FONT;
        ctx.fillText('KHQR', 32, 44);

        ctx.textAlign = 'center';
        ctx.fillStyle = '#0f172a';
        ctx.font = 'bold 26px ' + FONT;
        ctx.fillText(cfg.document_brand_name || 'EB DENTAL', W / 2, 132);
        ctx.font = 'bold 44px ' + FONT;
        ctx.fillText('$' + Number(meta.amount).toFixed(2), W / 2, 186);

        const qrX = (W - QR) / 2, qrY = 224;
        ctx.strokeStyle = '#e2e8f0';
        ctx.lineWidth = 2;
        ctx.strokeRect(qrX - 14, qrY - 14, QR + 28, QR + 28);
        // A QR is a grid of hard-edged squares; smoothing it on the way from 220px up to
        // 360px is how a code ends up blurry enough for a scanner to refuse it.
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(source, qrX, qrY, QR, QR);

        // The caption carries the clinic name, i.e. free text, so it is measured and
        // stepped down rather than allowed to run off both edges of the image.
        ctx.fillStyle = '#334155';
        let captionSize = 21;
        do {
            captionSize -= 1;
            ctx.font = '600 ' + captionSize + 'px ' + FONT;
        } while (captionSize > 12 && ctx.measureText(meta.caption).width > W - 64);
        ctx.fillText(meta.caption, W / 2, 628);

        ctx.fillStyle = '#64748b';
        ctx.font = '17px ' + FONT;
        ctx.fillText('Scan with any Bakong-enabled banking app', W / 2, 664);

        canvas.toBlob((blob) => {
            if (!blob) return;
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = meta.filename + '.png';
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        }, 'image/png');
    },

    // Payment confirmed - the ONLY place an invoice is ever produced for a KHQR order.
    // `order` is the one the server has just created off the back of the payment (the
    // poll returns it on the transition to paid); it did not exist a moment ago. Also
    // hands the invoice to store-api so the paid-order Telegram alert (already waiting
    // server-side) carries the real client-rendered document.
    async _finishPaidOrder(order) {
        const statusRow = document.getElementById('khqrStatusRow');
        if (statusRow) {
            statusRow.innerHTML = '<i class="fas fa-circle-check" style="color:#16a34a;"></i> Payment received — generating your invoice…';
        }

        try {
            this.buildPrintTemplate(order);
            const pdfBlob = await this.exportPDF(order.quote_code, 'Invoice');
            this.uploadQuotationPDF(order.id, pdfBlob);
        } catch (err) {
            // The payment itself is complete - never let a PDF hiccup mask that.
        }
        this.hideKhqrModal();
        await ebAlert('Payment received — thank you! Your invoice has been downloaded.', {
            title: 'Payment complete',
            tone: 'success',
            confirmText: 'Done',
        });
    },
};

document.addEventListener('DOMContentLoaded', () => {
    QuoteCart.render();

    document.getElementById('quoteCartIcon')?.addEventListener('click', () => QuoteCart.open());
    document.getElementById('quoteDrawerClose')?.addEventListener('click', () => QuoteCart.close());
    document.getElementById('quoteDrawerOverlay')?.addEventListener('click', () => QuoteCart.close());
    document.getElementById('quoteDownloadPdfBtn')?.addEventListener('click', () => QuoteCart.confirmPurchase());
    // Closing the KHQR modal early keeps the order awaiting payment server-side -
    // deliberately confirm-gated, and the overlay itself doesn't close on click, so a
    // stray tap can't kill the payment screen mid-scan.
    //
    // Staff get no such dialog: they are not mid-payment, the QR is stored on the order,
    // and the admin Orders page re-opens the identical one. Warning them about a
    // reservation they didn't make would only be noise.
    document.getElementById('khqrModalClose')?.addEventListener('click', async () => {
        if (QuoteCart._khqrStaffMode) {
            QuoteCart.hideKhqrModal();
            return;
        }
        const confirmed = await ebConfirm(
            'Your order stays reserved as awaiting payment. If you have already paid, your invoice will be issued as soon as the payment is confirmed.',
            { title: 'Close the payment window?', tone: 'warning', confirmText: 'Close' }
        );
        if (confirmed) QuoteCart.hideKhqrModal();
    });
    // Saves the code as a labelled PNG for sending on. Only ever visible in the staff
    // flow - see _renderKhqrCard().
    document.getElementById('khqrDownloadBtn')?.addEventListener('click', () => QuoteCart.downloadQrImage());

    // Delivery-location modal (customer carts). Closing it discards nothing that was
    // stored - only Save writes - so unlike the KHQR modal it needs no confirmation,
    // and a click on the backdrop is a close like any other.
    document.getElementById('cartLocationSave')?.addEventListener('click', () => QuoteCart.saveLocation());
    document.getElementById('cartLocationCancel')?.addEventListener('click', () => QuoteCart.closeLocationModal());
    document.getElementById('cartLocationClose')?.addEventListener('click', () => QuoteCart.closeLocationModal());
    document.getElementById('cartLocationOverlay')?.addEventListener('click', (e) => {
        if (e.target === e.currentTarget) QuoteCart.closeLocationModal();
    });
    document.getElementById('quoteDiscountEditBtn')?.addEventListener('click', () => {
        document.getElementById('quoteDiscountEditor')?.classList.toggle('open');
    });
    document.getElementById('quoteInfoToggle')?.addEventListener('click', () => {
        const form = document.getElementById('quoteInfoForm');
        if (!form) return;
        form.classList.toggle('collapsed');
        // The saved-location map is inside the section that just opened, and a
        // Leaflet map measured while its container was display:none comes back
        // zero-height. See refreshLocationPreview().
        if (!form.classList.contains('collapsed')) QuoteCart.refreshLocationPreview();
    });
});

/* ------------------------------------------------------------
   TOAST — brief confirmation message (e.g. "Added to cart
   successfully") shown instead of auto-opening the quote drawer.
------------------------------------------------------------- */
let _toastTimer = null;
function showToast(message) {
    const toast = document.getElementById('ebToast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => toast.classList.remove('show'), 2500);
}

/* ============================================================
   DIALOG — branded stand-in for the browser's native alert()/
   confirm(), which rendered as an OS dialog captioned
   "127.0.0.1:5000 says" and couldn't be styled at all.

   Both return a Promise (native confirm() is synchronous, so any
   caller being converted has to become async):
     await ebAlert('Something happened');            // resolves undefined
     if (await ebConfirm('Delete this?')) { ... }    // resolves true/false

   Styles live in base.css; the markup is built here on first use
   so no template has to include it.
   ============================================================ */
let _ebDialogEls = null;
let _ebDialogResolve = null;

function _ebBuildDialog() {
    if (_ebDialogEls) return _ebDialogEls;

    const overlay = document.createElement('div');
    overlay.className = 'eb-dialog-overlay';
    overlay.innerHTML = `
        <div class="eb-dialog" role="alertdialog" aria-modal="true"
             aria-labelledby="ebDialogTitle" aria-describedby="ebDialogMessage">
            <div class="eb-dialog-icon"><i></i></div>
            <h3 class="eb-dialog-title" id="ebDialogTitle"></h3>
            <p class="eb-dialog-message" id="ebDialogMessage"></p>
            <div class="eb-dialog-actions">
                <button type="button" class="eb-dialog-btn cancel"></button>
                <button type="button" class="eb-dialog-btn confirm"></button>
            </div>
        </div>`;
    document.body.appendChild(overlay);

    _ebDialogEls = {
        overlay,
        box: overlay.querySelector('.eb-dialog'),
        icon: overlay.querySelector('.eb-dialog-icon i'),
        title: overlay.querySelector('.eb-dialog-title'),
        message: overlay.querySelector('.eb-dialog-message'),
        cancelBtn: overlay.querySelector('.eb-dialog-btn.cancel'),
        confirmBtn: overlay.querySelector('.eb-dialog-btn.confirm'),
    };

    _ebDialogEls.confirmBtn.addEventListener('click', () => _ebCloseDialog(true));
    _ebDialogEls.cancelBtn.addEventListener('click', () => _ebCloseDialog(false));
    // Clicking the backdrop (but not the box) dismisses, same as Escape below.
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) _ebCloseDialog(false);
    });
    document.addEventListener('keydown', (e) => {
        if (!_ebDialogEls || !_ebDialogEls.overlay.classList.contains('active')) return;
        if (e.key === 'Escape') {
            _ebCloseDialog(false);
            return;
        }
        // Enter confirms, except when the user has tabbed onto Cancel - there
        // the button's own click handler is what should win.
        if (e.key === 'Enter' && document.activeElement !== _ebDialogEls.cancelBtn) {
            e.preventDefault();
            _ebCloseDialog(true);
        }
    });

    return _ebDialogEls;
}

function _ebCloseDialog(result) {
    if (!_ebDialogEls) return;
    _ebDialogEls.overlay.classList.remove('active');
    document.body.style.overflow = _ebPrevOverflow || '';
    if (_ebPrevFocus && _ebPrevFocus.focus) _ebPrevFocus.focus();
    const resolve = _ebDialogResolve;
    _ebDialogResolve = null;
    if (resolve) resolve(result);
}

let _ebPrevFocus = null;
let _ebPrevOverflow = '';

const _EB_TONE_ICONS = {
    info: 'fa-circle-info',
    danger: 'fa-triangle-exclamation',
    warning: 'fa-triangle-exclamation',
    success: 'fa-circle-check',
};

function ebDialog({
    message,
    title = '',
    tone = 'info',
    confirmText = 'OK',
    cancelText = 'Cancel',
    showCancel = false,
} = {}) {
    const els = _ebBuildDialog();

    // Resolve any dialog still open rather than orphaning its promise.
    if (_ebDialogResolve) _ebCloseDialog(false);

    els.box.dataset.tone = tone;
    els.box.classList.toggle('is-alert', !showCancel);
    els.icon.className = 'fas ' + (_EB_TONE_ICONS[tone] || _EB_TONE_ICONS.info);
    els.title.textContent = title;
    els.title.style.display = title ? '' : 'none';
    // textContent, not innerHTML: messages can carry server-supplied text.
    els.message.textContent = message || '';
    els.confirmBtn.textContent = confirmText;
    els.cancelBtn.textContent = cancelText;
    els.cancelBtn.style.display = showCancel ? '' : 'none';

    _ebPrevFocus = document.activeElement;
    _ebPrevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    els.overlay.classList.add('active');
    els.confirmBtn.focus();

    return new Promise((resolve) => { _ebDialogResolve = resolve; });
}

function ebAlert(message, opts = {}) {
    return ebDialog({ title: 'Heads up', ...opts, message, showCancel: false }).then(() => undefined);
}

function ebConfirm(message, opts = {}) {
    return ebDialog({ title: 'Are you sure?', confirmText: 'Confirm', ...opts, message, showCancel: true });
}

/* Any <form data-confirm="..."> asks before it submits - the branded
   replacement for the inline onsubmit="return confirm(...)" that the admin
   delete buttons used to carry. form.submit() doesn't re-fire the submit
   event, so there's no loop to guard against here. */
document.addEventListener('submit', (e) => {
    const form = e.target.closest('form[data-confirm]');
    if (!form) return;
    e.preventDefault();
    ebConfirm(form.dataset.confirm, {
        tone: form.dataset.confirmTone || 'danger',
        confirmText: form.dataset.confirmLabel || 'Delete',
    }).then((ok) => {
        if (ok) form.submit();
    });
});

/* Clicking anywhere on an admin table row opens that row's edit dialog, so
   reaching a record no longer means hitting the small pencil button at the far
   right of a wide table. Delegated from the document like the handler above, so
   it covers every admin list page without any of them wiring anything up: the
   row's own edit button is the trigger, marked `data-row-edit` in the template.

   Driving it from that button rather than from a per-row data attribute keeps
   one source of truth for "what does editing this row do" - the row can't end
   up opening a different record than its button does. A row with no such button
   (a staff member's own row on User Management, or a product listed by someone
   who only holds price_listing) simply isn't clickable, and the CSS below keys
   off the same attribute so it isn't styled as though it were. */
document.addEventListener('click', (e) => {
    const row = e.target.closest('tr');
    if (!row) return;
    const trigger = row.querySelector('[data-row-edit]');
    if (!trigger) return;
    // Anything the user could have meant to click on its own terms wins: the
    // Delete button and its form, the "View PDF" link, the price button, and any
    // future checkbox or input in a cell.
    if (e.target.closest('a, button, input, select, textarea, label, form')) return;
    // Dragging across a cell to copy an email or a phone number ends in a click
    // event too - opening a dialog on top of the selection would throw the text
    // away just as the user finished selecting it.
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed && row.contains(selection.anchorNode)) return;
    trigger.click();
});

/* ------------------------------------------------------------
   INLINE FIELD VALIDATION
   Forms marked `novalidate` opt out of the browser's native
   "Please fill out this field." bubble; this renders the same
   constraint failures as styled inline messages instead. Returns
   true when the form is valid, and focuses the first bad field
   when it isn't. Relies on the native Constraint Validation API,
   so `required`/`type=email`/`minlength` etc. still drive it.
------------------------------------------------------------- */
function ebValidateForm(form) {
    let firstInvalid = null;

    form.querySelectorAll('input, select, textarea').forEach((field) => {
        if (field.disabled || field.type === 'hidden') return;
        const group = field.closest('.form-group') || field.parentElement;
        const valid = field.checkValidity();

        if (!valid && !firstInvalid) firstInvalid = field;
        if (group) group.classList.toggle('has-error', !valid);

        let errorEl = group && group.querySelector('.field-error');
        if (!valid && group) {
            if (!errorEl) {
                errorEl = document.createElement('div');
                errorEl.className = 'field-error';
                errorEl.innerHTML = '<i class="fas fa-circle-exclamation"></i><span></span>';
                group.appendChild(errorEl);
            }
            errorEl.querySelector('span').textContent = _ebFieldMessage(field);
            errorEl.classList.add('show');
        } else if (errorEl) {
            errorEl.classList.remove('show');
        }
    });

    if (firstInvalid) firstInvalid.focus();
    return !firstInvalid;
}

/* Friendlier wording than validationMessage's browser defaults, which vary
   per browser and read like error codes ("Please fill out this field."). */
function _ebFieldMessage(field) {
    const label = (field.closest('.form-group')?.querySelector('label')?.textContent || '').trim();
    const name = label || field.getAttribute('placeholder') || 'This field';
    if (field.validity.valueMissing) return `${name} is required.`;
    if (field.validity.typeMismatch && field.type === 'email') return 'Enter a valid email address.';
    if (field.validity.tooShort) return `${name} must be at least ${field.minLength} characters.`;
    if (field.validity.patternMismatch) return `${name} isn't in the expected format.`;
    return field.validationMessage;
}

/* Clears a field's error as soon as the user fixes it - re-validating the
   whole form on every keystroke would light up fields they haven't reached. */
document.addEventListener('input', (e) => {
    const group = e.target.closest?.('.form-group.has-error');
    if (!group || !e.target.checkValidity?.()) return;
    group.classList.remove('has-error');
    group.querySelector('.field-error')?.classList.remove('show');
});

/* ------------------------------------------------------------
   IMAGE PICKER PREVIEW
   <input type="file" data-preview="someImgId"> swaps the matching
   <img> over to the file that was just picked, so admins see the
   image before saving instead of after. Edit modals seed the
   already-saved image through ebSetImagePreview(), which the
   picker falls back to if the selection is cleared again.
------------------------------------------------------------- */
function ebSetImagePreview(imgId, src) {
    const preview = document.getElementById(imgId);
    if (!preview) return;

    _ebReleasePreviewUrl(preview);
    preview.dataset.savedSrc = src || '';
    _ebShowPreview(preview, src);
}

/* Object URLs live until revoked, so the previous pick's URL is dropped
   whenever the preview moves on to a different image. */
function _ebReleasePreviewUrl(preview) {
    if (!preview.dataset.objectUrl) return;
    URL.revokeObjectURL(preview.dataset.objectUrl);
    delete preview.dataset.objectUrl;
}

/* src='' would resolve to the current page URL and fire a pointless
   request, so an empty preview drops the attribute instead. */
function _ebShowPreview(preview, src) {
    if (src) {
        preview.src = src;
        preview.style.display = '';
    } else {
        preview.removeAttribute('src');
        preview.style.display = 'none';
    }
}

document.addEventListener('change', (e) => {
    const input = e.target;
    if (!input.matches?.('input[type="file"][data-preview]')) return;

    const preview = document.getElementById(input.dataset.preview);
    if (!preview) return;
    _ebReleasePreviewUrl(preview);

    const file = input.files?.[0];
    if (!file || !file.type.startsWith('image/')) {
        // Selection cleared (or a non-image slipped through the accept
        // filter): show the saved image again, or nothing when creating.
        _ebShowPreview(preview, preview.dataset.savedSrc);
        return;
    }

    const url = URL.createObjectURL(file);
    preview.dataset.objectUrl = url;
    _ebShowPreview(preview, url);
});

/* ------------------------------------------------------------
   PRODUCT PICKER (admin) — one searchable combobox over the whole
   catalogue, used everywhere a bundle row has to name a product.

   It replaces a <select> that was filled from a single limit=500
   fetch embedded in the page. That was a complete list while the
   catalogue was ~110 machines; after the SAP import it was 500 of
   8,000+ rows in name order, so every picker opened on materials
   whose names begin with a quote character and no machinery
   product could be reached at all.

   So the list is searched server-side, one query at a time, and
   the browser never holds the catalogue. Needs PRODUCT_SEARCH_URL
   on the page (admin.products_search).

   What is chosen lives in a hidden input carrying whatever class
   the caller asks for (.bundle-row-product / .option-choice-product)
   and fires `change` when it moves, so ebBundlePicker and
   ebOptionGroupPicker keep reading it exactly as they read the
   <select> it replaced.
------------------------------------------------------------- */
const ebProductPicker = {
    /* Everything the picker has seen this page-load, id -> row. Filled by
       searches and by lookup(), and read for the labels and prices of products
       already sitting in a bundle - the two things a bare id cannot render. */
    _cache: new Map(),
    _searchDelay: 200,
    _openPicker: null,

    _url() {
        return (typeof PRODUCT_SEARCH_URL !== 'undefined' && PRODUCT_SEARCH_URL) || '';
    },

    /* `partial` marks a row that came down inside a bundle rather than from a
       search: it carries a name and a code but no price, which is enough to render
       the row and not enough to price an upgrade against. Such a row never
       overwrites a full one, and lookup() below treats it as still missing. */
    _remember(product, partial) {
        if (!product || product.id == null) return product;
        const key = String(product.id);
        const known = this._cache.get(key);
        if (partial && known && !known._partial) return known;
        this._cache.set(key, { ...product, _partial: !!partial });
        return product;
    },

    get(productId) {
        return this._cache.get(String(productId)) || null;
    },

    /* The price of a product the picker has seen, or null - null meaning "not
       known", never "free". ebOptionGroupPicker shows an upcharge hint only when
       both ends of the comparison answer a real number. */
    priceOf(productId) {
        const found = this.get(productId);
        return found && typeof found.price === 'number' ? found.price : null;
    },

    /* Resolve ids already sitting in a bundle into full rows. One request for
       whatever is still unknown; resolves once the cache holds them, so a caller
       can await it before rendering anything that needs a price. */
    lookup(productIds) {
        const missing = [...new Set((productIds || []).map(String))]
            .filter(id => {
                if (!id || id === 'null' || id === 'undefined') return false;
                const known = this._cache.get(id);
                return !known || known._partial;
            });
        if (!missing.length || !this._url()) return Promise.resolve();
        return fetch(this._url() + '?ids=' + encodeURIComponent(missing.join(',')), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(res => (res.ok ? res.json() : { products: [] }))
            .then(data => (data.products || []).forEach(p => this._remember(p)))
            // A failed lookup costs a price hint, not the editor - the row still
            // shows whatever name came down with the bundle itself.
            .catch(() => {});
    },

    /* Repaint every idle picker under `root`. Called after lookup() fills in what
       a bundle payload could not carry, so a row that opened knowing only a name
       picks up its code, shop and price. Pickers with their list open are left
       alone - repainting one under the cursor would close it. */
    refreshIn(root) {
        (root || document).querySelectorAll('.prodpick').forEach(el => {
            if (el._pick && el._pick.menu.hidden) this._paint(el._pick);
        });
    },

    /* A picker, as a detached element the caller drops into its own row.

       `product` is what the row already holds, in either shape the server sends:
       a bundle item ({product_id, product_name, ...}) or a catalogue row
       ({id, ...}). Passing it means the row renders its selection immediately,
       without waiting for a round trip. */
    create({ name, className, product, onChange }) {
        const wrap = document.createElement('div');
        wrap.className = 'prodpick';
        wrap.innerHTML = `
            <input type="hidden"${name ? ` name="${ebEscapeHtml(name)}"` : ''} class="${ebEscapeHtml(className || '')}">
            <button type="button" class="prodpick-chosen" hidden>
                <span class="prodpick-chosen-text"></span>
                <i class="fas fa-pen prodpick-chosen-edit"></i>
            </button>
            <div class="prodpick-search">
                <i class="fas fa-search prodpick-search-icon"></i>
                <input type="text" class="prodpick-input" autocomplete="off" spellcheck="false"
                       placeholder="Search the catalogue by name or code…">
            </div>
            <div class="prodpick-menu" hidden>
                <div class="prodpick-tabs">
                    <button type="button" class="prodpick-tab is-on" data-section="all">All</button>
                    <button type="button" class="prodpick-tab" data-section="machinery">Machinery</button>
                    <button type="button" class="prodpick-tab" data-section="materials">Materials</button>
                    <button type="button" class="prodpick-tab" data-section="spare_parts">Spare parts</button>
                </div>
                <div class="prodpick-results"></div>
                <div class="prodpick-note"></div>
            </div>`;

        const state = {
            wrap,
            hidden: wrap.querySelector('input[type="hidden"]'),
            chosen: wrap.querySelector('.prodpick-chosen'),
            chosenText: wrap.querySelector('.prodpick-chosen-text'),
            search: wrap.querySelector('.prodpick-search'),
            input: wrap.querySelector('.prodpick-input'),
            menu: wrap.querySelector('.prodpick-menu'),
            results: wrap.querySelector('.prodpick-results'),
            note: wrap.querySelector('.prodpick-note'),
            section: 'all',
            rows: [],
            active: -1,
            seq: 0,
            timer: null,
            onChange,
        };
        wrap._pick = state;

        const initialId = product && (product.product_id != null ? product.product_id : product.id);
        if (initialId != null && initialId !== '') {
            // Bundle items travel with their own name and code, so a saved row
            // reads properly the moment the modal opens, before any search runs.
            const hasPrice = typeof product.price === 'number';
            this._remember({
                id: initialId,
                product_name: product.product_name || '',
                product_code: product.product_code || null,
                section: product.section || null,
                price: hasPrice ? product.price : null,
            }, !hasPrice);
            state.hidden.value = String(initialId);
        }
        this._paint(state);

        state.chosen.addEventListener('click', () => this._open(state));
        state.input.addEventListener('input', () => {
            this._openMenu(state);
            this._schedule(state);
        });
        state.input.addEventListener('focus', () => this._openMenu(state));
        state.input.addEventListener('keydown', e => this._onKey(state, e));
        wrap.querySelectorAll('.prodpick-tab').forEach(tab => {
            tab.addEventListener('mousedown', e => e.preventDefault());  // keep focus in the box
            tab.addEventListener('click', () => {
                state.section = tab.dataset.section;
                wrap.querySelectorAll('.prodpick-tab').forEach(t => t.classList.toggle('is-on', t === tab));
                state.input.focus();
                this._search(state);
            });
        });
        // mousedown rather than click: blur fires first otherwise, and the row
        // being clicked is gone by the time the click lands.
        state.results.addEventListener('mousedown', e => {
            const option = e.target.closest('.prodpick-opt');
            if (!option) return;
            e.preventDefault();
            this._choose(state, option.dataset.id);
        });
        state.input.addEventListener('blur', () => {
            // Leaving the box abandons whatever was half-typed: the selection is
            // the hidden field, and that only ever moves through _choose().
            setTimeout(() => this._close(state), 120);
        });

        return wrap;
    },

    _label(product) {
        return product ? (product.product_name || ('#' + product.id)) : '';
    },

    _sectionLabel(section) {
        return { machinery: 'Machinery', materials: 'Materials', spare_parts: 'Spare parts' }[section] || '';
    },

    _metaHtml(product, withPrice) {
        const bits = [];
        if (product.product_code) {
            bits.push(`<span class="prodpick-code">${ebEscapeHtml(product.product_code)}</span>`);
        }
        const sectionLabel = this._sectionLabel(product.section);
        if (sectionLabel) bits.push(`<span class="prodpick-sec">${sectionLabel}</span>`);
        if (withPrice && typeof product.price === 'number') {
            bits.push(`<span class="prodpick-price">$${product.price.toFixed(2)}</span>`);
        }
        return bits.join('');
    },

    /* Chosen or empty - the two faces of the control. Chosen shows the product as
       a line you click to change it; empty shows the search box itself, so a row
       just added is already waiting to be typed into. */
    _paint(state) {
        const product = this.get(state.hidden.value);
        const isChosen = !!(state.hidden.value && product);
        state.wrap.classList.toggle('is-chosen', isChosen);
        state.chosen.hidden = !isChosen;
        state.search.hidden = isChosen;
        if (!isChosen) return;

        const meta = this._metaHtml(product, false);
        state.chosenText.innerHTML =
            `<span class="prodpick-name">${ebEscapeHtml(this._label(product))}</span>` +
            (meta ? `<span class="prodpick-meta">${meta}</span>` : '');
    },

    _open(state) {
        state.wrap.classList.remove('is-chosen');
        state.chosen.hidden = true;
        state.search.hidden = false;
        state.input.value = '';
        state.input.focus();
        this._openMenu(state);
    },

    _openMenu(state) {
        // One list open at a time, so a menu left hanging above another row can't
        // be mistaken for that row's own.
        if (this._openPicker && this._openPicker !== state) this._close(this._openPicker);
        this._openPicker = state;
        if (state.menu.hidden) {
            state.menu.hidden = false;
            this._search(state);
        }
        this._placeMenu(state);
    },

    /* Drops the list upward when the row sits near the bottom of the space it has
       to open into. That space is the modal, not the window: .dash-modal-box is a
       scroll box of its own, so a list opening downward from its last row is
       clipped by the modal's edge however much screen is left below it. */
    _placeMenu(state) {
        const box = state.wrap.getBoundingClientRect();
        const host = state.wrap.closest('.dash-modal-box');
        const bounds = host ? host.getBoundingClientRect() : null;
        const floor = bounds ? Math.min(bounds.bottom, window.innerHeight) : window.innerHeight;
        const ceiling = bounds ? Math.max(bounds.top, 0) : 0;
        const below = floor - box.bottom;
        const above = box.top - ceiling;
        state.wrap.classList.toggle('menu-up', below < 240 && above > below);
    },

    _close(state) {
        state.menu.hidden = true;
        state.active = -1;
        if (this._openPicker === state) this._openPicker = null;
        this._paint(state);  // back to the chosen line, or to an empty search box
    },

    _schedule(state) {
        clearTimeout(state.timer);
        state.timer = setTimeout(() => this._search(state), this._searchDelay);
    },

    _search(state) {
        const url = this._url();
        if (!url) return;
        const query = state.input.value.trim();
        const seq = ++state.seq;
        state.note.textContent = 'Searching…';
        fetch(`${url}?q=${encodeURIComponent(query)}&section=${encodeURIComponent(state.section)}`, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(res => (res.ok ? res.json() : Promise.reject(new Error(res.status))))
            .then(data => {
                // A slow earlier request must not overwrite a later answer.
                if (seq !== state.seq) return;
                (data.products || []).forEach(p => this._remember(p));
                this._renderResults(state, data);
            })
            .catch(() => {
                if (seq !== state.seq) return;
                state.results.innerHTML = '';
                state.note.textContent = 'Could not search the catalogue.';
            });
    },

    _renderResults(state, data) {
        const products = data.products || [];
        state.rows = products;
        state.active = products.length ? 0 : -1;
        state.results.innerHTML = products.map((p, i) => `
            <div class="prodpick-opt${i === 0 ? ' is-active' : ''}" data-id="${p.id}">
                <span class="prodpick-name">${ebEscapeHtml(this._label(p))}</span>
                <span class="prodpick-meta">${this._metaHtml(p, true)}</span>
            </div>`).join('');
        state.note.textContent = !products.length
            ? 'No products match.'
            : (data.more ? 'First 25 matches — keep typing to narrow it down.' : '');
        this._placeMenu(state);
    },

    _onKey(state, e) {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            this._move(state, e.key === 'ArrowDown' ? 1 : -1);
        } else if (e.key === 'Enter') {
            // Also stops a half-typed search from submitting the modal's form.
            e.preventDefault();
            const row = state.rows[state.active];
            if (row) this._choose(state, row.id);
        } else if (e.key === 'Escape') {
            e.preventDefault();
            state.input.blur();
        }
    },

    _move(state, step) {
        if (!state.rows.length) return;
        state.active = (state.active + step + state.rows.length) % state.rows.length;
        const options = state.results.querySelectorAll('.prodpick-opt');
        options.forEach((el, i) => el.classList.toggle('is-active', i === state.active));
        if (options[state.active]) options[state.active].scrollIntoView({ block: 'nearest' });
    },

    _choose(state, productId) {
        state.hidden.value = String(productId);
        state.menu.hidden = true;
        if (this._openPicker === state) this._openPicker = null;
        this._paint(state);
        // Bubbles, because that is what the <select> did here - the option-group
        // editor listens on the row for it to re-derive its upcharge hints.
        state.hidden.dispatchEvent(new Event('change', { bubbles: true }));
        if (state.onChange) state.onChange(this.get(productId));
    },
};

/* ------------------------------------------------------------
   BUNDLE PICKER (admin) — the repeatable "which products are in
   this?" list shared by three modals: a Promotion's contents, a
   Set's contents, and a Product's free "comes with" items. All
   three post the same parallel inputs (item_product_id[] +
   item_qty[]), read back by bundle_items_from_form() in
   blueprints/admin/__init__.py.

   Which product a row holds is chosen through ebProductPicker
   above, so the page needs PRODUCT_SEARCH_URL rather than a
   catalogue of its own.

   Zero rows is a meaningful state, not an empty form: it posts no
   item_product_id at all, which store-api reads as "this bundle
   now contains nothing" rather than "leave it alone".
------------------------------------------------------------- */
const ebBundlePicker = {
    // items: [{product_id, product_name, qty}] straight off a store-api bundle
    // (or [] when creating).
    render(containerId, items) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';
        (items || []).forEach(item => this.addRow(containerId, item));
        this._syncEmptyHint(container);

        // A bundle item carries a name and a code but not which shop it is from
        // (see BundleItemOut), so the saved rows fill that in afterwards - a row
        // added by hand shows it immediately, and the two should not disagree.
        const ids = (items || []).map(item => item.product_id).filter(Boolean);
        if (ids.length) {
            ebProductPicker.lookup(ids).then(() => ebProductPicker.refreshIn(container));
        }
    },

    addRow(containerId, item) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const row = document.createElement('div');
        row.className = 'bundle-row';
        row.innerHTML = `
            <input type="number" name="item_qty" class="bundle-row-qty" min="1" step="1" value="${(item && item.qty) || 1}" title="Quantity included">
            <button type="button" class="bundle-row-remove" title="Remove"><i class="fas fa-times"></i></button>`;
        // Built as an element rather than as markup in the string above: the picker
        // wires up its own listeners. Prepended so the product leads the row, the
        // way the <select> it replaced did.
        row.prepend(ebProductPicker.create({
            name: 'item_product_id',
            className: 'bundle-row-product',
            product: item,
        }));
        row.querySelector('.bundle-row-remove').addEventListener('click', () => {
            row.remove();
            this._syncEmptyHint(container);
        });
        container.appendChild(row);
        this._syncEmptyHint(container);
    },

    _syncEmptyHint(container) {
        const hint = document.getElementById(container.id + 'Empty');
        if (hint) hint.style.display = container.children.length ? 'none' : 'block';
    },
};

/* ------------------------------------------------------------
   OPTION GROUP PICKER (admin) — a Set's swappable slots: "Laptop",
   "X-ray model", each offering several products where picking a
   dearer one adds to the set price (see SetOptionGroup in store-api).

   Two levels, so unlike ebBundlePicker above this can NOT post flat
   parallel inputs — "which choice belongs to which group" has
   nowhere to live in item_product_id[]/item_qty[]. Instead the whole
   structure is serialized into one hidden field on submit and parsed
   by option_groups_from_form() in blueprints/admin/sets.py.

   Prices come from ebProductPicker's cache - filled by the searches
   the admin runs, and warmed by render() for the products a saved
   set already holds - and are used to show what an upcharge WOULD
   be if left on auto.

   Leaving Upcharge blank stores NULL, which means "derive it from the
   price gap at order time" — the recommended state, because it can't
   go stale when either product is repriced.
------------------------------------------------------------- */
const ebOptionGroupPicker = {
    /* Which container holds the "Included Products" list this editor upgrades.
       A slot's standard choice is normally one of those products - store-api
       treats the two as the same slot rather than two separate items (see
       set_contents), so an upgrade REPLACES the included product instead of
       sitting next to it. */
    itemsContainerId: 'setItemsPicker',

    _priceOf(productId) {
        return ebProductPicker.priceOf(productId);
    },

    // What is currently listed under "Included Products", in their order, as
    // {product_id, qty} - the qty comes along so upgrading a "×2" item doesn't
    // silently become ×1.
    _includedProducts() {
        const items = document.getElementById(this.itemsContainerId);
        if (!items) return [];
        return Array.from(items.querySelectorAll('.bundle-row'))
            .map(row => {
                const productId = row.querySelector('.bundle-row-product').value;
                // The name too, not just the id: a slot seeded from this list has
                // to render as the product it took, and only the picker's cache
                // knows what that id is called.
                const known = ebProductPicker.get(productId);
                return {
                    product_id: productId,
                    product_name: known ? known.product_name : '',
                    product_code: known ? known.product_code : null,
                    section: known ? known.section : null,
                    qty: parseInt(row.querySelector('.bundle-row-qty').value, 10) || 1,
                };
            })
            .filter(item => item.product_id);
    },

    // Included products already taken as the standard choice of some slot, so a
    // second slot doesn't propose upgrading the same item twice.
    _claimedProductIds(container) {
        return Array.from(container.querySelectorAll('.option-choice'))
            .filter(row => row.querySelector('.option-choice-default').checked)
            .map(row => row.querySelector('.option-choice-product').value)
            .filter(Boolean);
    },

    render(containerId, groups) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';
        (groups || []).forEach(group => this.addGroup(containerId, group));
        this._syncEmptyHint(container);

        // The choices arrive with names but no prices (see SetOptionChoiceOut), so
        // the "auto (…)" hints have nothing to compute from until the prices are
        // fetched. Done after the rows exist, then the hints are re-derived - the
        // editor is usable throughout, it just says a plain "auto" for a moment.
        const ids = (groups || []).flatMap(g => (g.choices || []).map(c => c.product_id));
        if (ids.length) {
            ebProductPicker.lookup(ids).then(() => {
                ebProductPicker.refreshIn(container);
                container.querySelectorAll('.option-choices').forEach(el => this._refreshHints(el));
            });
        }
    },

    addGroup(containerId, group) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const box = document.createElement('div');
        box.className = 'option-group';
        box.innerHTML = `
            <div class="option-group-head">
                <input type="text" class="option-group-name" placeholder="Slot name, e.g. Laptop"
                       value="${ebEscapeHtml((group && group.name) || '')}">
                <button type="button" class="bundle-row-remove option-group-remove" title="Remove this slot"><i class="fas fa-times"></i></button>
            </div>
            <div class="option-choices"></div>
            <button type="button" class="btn-dash sm option-add-choice"><i class="fas fa-plus"></i> Add choice</button>`;

        box.querySelector('.option-group-remove').addEventListener('click', () => {
            box.remove();
            this._syncEmptyHint(container);
        });
        box.querySelector('.option-add-choice').addEventListener('click', () => {
            this._addChoice(box.querySelector('.option-choices'));
        });

        container.appendChild(box);
        const choicesEl = box.querySelector('.option-choices');
        const choices = (group && group.choices) || [];
        if (choices.length) {
            choices.forEach(c => this._addChoice(choicesEl, c));
        } else {
            // A brand-new slot starts with its standard choice already filled in
            // from "Included Products" - that is what the slot upgrades, so
            // making the admin re-pick a product they just listed above is both
            // busywork and the easy way to end up with a set that lists the same
            // machine twice. First included product not already claimed by
            // another slot; a plain empty row if there is nothing left to claim.
            const claimed = this._claimedProductIds(container);
            const available = this._includedProducts()
                .filter(item => !claimed.includes(String(item.product_id)));
            this._addChoice(
                choicesEl,
                available.length ? { ...available[0], is_default: true } : undefined,
            );
            // The second row is the upgrade itself - the whole point of the slot.
            this._addChoice(choicesEl);
        }
        this._syncEmptyHint(container);
    },

    _addChoice(choicesEl, choice) {
        const row = document.createElement('div');
        row.className = 'option-choice';
        // Radio names are per-group so exactly one choice per slot can be the
        // default — the same rule the partial unique index enforces server-side.
        const groupKey = choicesEl.dataset.key
            || (choicesEl.dataset.key = 'og' + Math.random().toString(36).slice(2));
        const storedDelta = (choice && choice.price_delta !== null && choice.price_delta !== undefined)
            ? choice.price_delta : '';
        row.innerHTML = `
            <input type="radio" name="${groupKey}-default" class="option-choice-default" title="The standard choice, already covered by the set price"${choice && choice.is_default ? ' checked' : ''}>
            <input type="number" class="option-choice-qty" min="1" step="1" value="${(choice && choice.qty) || 1}" title="Quantity">
            <input type="number" class="option-choice-delta" step="0.01" placeholder="auto" value="${storedDelta}" title="Upcharge vs the standard choice. Leave blank to work it out from the products' prices.">
            <button type="button" class="bundle-row-remove" title="Remove"><i class="fas fa-times"></i></button>`;
        // No `name`: a slot's rows are serialized into one hidden field on submit
        // (see serialize below), not posted as form fields of their own.
        row.querySelector('.option-choice-qty').before(ebProductPicker.create({
            className: 'option-choice-product',
            product: choice,
        }));

        row.querySelector('.bundle-row-remove').addEventListener('click', () => {
            row.remove();
            this._refreshHints(choicesEl);
        });
        row.querySelector('.option-choice-product').addEventListener('change', () => this._refreshHints(choicesEl));
        row.querySelector('.option-choice-qty').addEventListener('change', () => this._refreshHints(choicesEl));
        row.querySelector('.option-choice-default').addEventListener('change', () => this._refreshHints(choicesEl));

        choicesEl.appendChild(row);
        // First row in a fresh group is the default until told otherwise.
        if (!choicesEl.querySelector('.option-choice-default:checked')) {
            row.querySelector('.option-choice-default').checked = true;
        }
        this._refreshHints(choicesEl);
    },

    /* Shows what an "auto" upcharge currently works out to, so the admin can see
       the number they are choosing not to override. Purely informational — the
       field still posts blank, i.e. NULL, i.e. derive it again at order time. */
    _refreshHints(choicesEl) {
        const rows = Array.from(choicesEl.querySelectorAll('.option-choice'));
        const defaultRow = rows.find(r => r.querySelector('.option-choice-default').checked);
        const basePrice = defaultRow
            ? this._priceOf(defaultRow.querySelector('.option-choice-product').value)
            : null;
        const baseQty = defaultRow
            ? (parseInt(defaultRow.querySelector('.option-choice-qty').value, 10) || 1)
            : 1;

        rows.forEach(row => {
            const delta = row.querySelector('.option-choice-delta');
            if (row === defaultRow) {
                // The baseline cannot be an upcharge on itself.
                delta.placeholder = 'standard';
                delta.disabled = true;
                delta.value = '';
                return;
            }
            delta.disabled = false;
            const price = this._priceOf(row.querySelector('.option-choice-product').value);
            const qty = parseInt(row.querySelector('.option-choice-qty').value, 10) || 1;
            delta.placeholder = (price !== null && basePrice !== null)
                ? 'auto (' + (price * qty - basePrice * baseQty).toFixed(2) + ')'
                : 'auto';
        });
    },

    /* The editor's state as store-api's option_groups payload. Called on submit
       and written into the hidden field. A group with no name, or with no chosen
       product in any row, is dropped rather than posted half-built. */
    serialize(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return [];
        return Array.from(container.querySelectorAll('.option-group')).map(box => {
            const name = box.querySelector('.option-group-name').value.trim();
            const choices = Array.from(box.querySelectorAll('.option-choice')).map(row => {
                const productId = row.querySelector('.option-choice-product').value;
                if (!productId) return null;
                const rawDelta = row.querySelector('.option-choice-delta').value.trim();
                return {
                    product_id: parseInt(productId, 10),
                    qty: parseInt(row.querySelector('.option-choice-qty').value, 10) || 1,
                    // Blank -> null -> derived at order time.
                    price_delta: rawDelta === '' ? null : parseFloat(rawDelta),
                    is_default: row.querySelector('.option-choice-default').checked,
                };
            }).filter(Boolean);
            return name && choices.length ? { name, choices } : null;
        }).filter(Boolean);
    },

    _syncEmptyHint(container) {
        const hint = document.getElementById(container.id + 'Empty');
        if (hint) hint.style.display = container.children.length ? 'none' : 'block';
    },
};

/* Escape a value before interpolating it into any HTML string that will be
   assigned to innerHTML. Used for everything that came from the server: product
   and promotion names (admin-entered), and the clinic/address/contact fields on
   an order (customer-entered, so genuinely untrusted). A function declaration on
   purpose - it's hoisted, so callers earlier in this file can use it. */
function ebEscapeHtml(text) {
    return String(text ?? '').replace(/[&<>"']/g, ch => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
    ));
}

/* ------------------------------------------------------------
   PROMO BANNER STRIP — dismiss button
   Hides the banner for the rest of this page view (not persisted;
   it'll show again on the next page load/navigation).
------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = document.getElementById('promoBannerClose');
    const banner = document.getElementById('promoBannerStrip');
    if (closeBtn && banner) {
        closeBtn.addEventListener('click', () => {
            banner.style.display = 'none';
        });
    }
});
/* ============================================================
   ACCOUNT DRAWER — the header avatar now slides a panel in from
   the right (orders + profile settings) instead of navigating to
   /profile. Markup: partials/account_drawer.html.

   Orders are fetched once, on the first open, from
   PROFILE_ORDERS_URL (/profile/orders) — there's no reason to
   pay for that request on page loads where the drawer is never
   opened. `_loaded` is what keeps it to one fetch per page view.
   ============================================================ */

/* ---- Staff order workflow ---------------------------------------------------
   "Confirm order" and "Mark as complete" on the storefront's own order views: the
   account drawer's detail panel (below) and the full-page one (auth/order_detail.html,
   which calls these same two helpers from its inline script).

   Staff raise quotes from the storefront cart, so this is where they already are when
   an order needs moving along - the admin Orders screen stays the whole-store view with
   cancelling, editing and payments on it.

   The ladder is pending -> confirmed -> delivered, and it only ever goes forwards.
   Cancelling is deliberately not offered here (see ORDER_WORKFLOW_STATUSES in
   blueprints/auth_routes.py, which is what actually restricts what may be sent), and on
   a PAID order store-api itself refuses anything but a forward move.
   ---------------------------------------------------------------------------- */
const ORDER_WORKFLOW = ['pending', 'confirmed', 'delivered'];

// Returns the workflow control block for `order`, or '' when there is nothing to
// offer: a customer (CAN_SET_ORDER_STATUS is false for them), a cancelled order, or a
// status that isn't on the ladder at all - a free-text status somebody typed into the
// admin dropdown's place has no "next step" to move to, so guessing one would be wrong.
function orderWorkflowHtml(order) {
    if (typeof CAN_SET_ORDER_STATUS === 'undefined' || !CAN_SET_ORDER_STATUS) return '';
    if (order.status === 'cancelled') return '';
    const rank = ORDER_WORKFLOW.indexOf(order.status);
    if (rank === -1) return '';

    if (rank === ORDER_WORKFLOW.length - 1) {
        return `<div class="account-workflow">
            <div class="account-workflow-done"><i class="fas fa-circle-check"></i> Completed — nothing left to do on this order.</div>
        </div>`;
    }

    // Both buttons on a pending order, not just the next step: a counter sale that was
    // picked, paid and handed over in one go is finished the moment it is rung up, and
    // making staff press Confirm first only to press Complete a second later records
    // nothing that wasn't already true.
    const buttons = [];
    if (rank < ORDER_WORKFLOW.indexOf('confirmed')) {
        buttons.push(`<button type="button" class="account-workflow-btn" data-order-status="confirmed">
            <i class="fas fa-check"></i> Confirm order
        </button>`);
    }
    buttons.push(`<button type="button" class="account-workflow-btn complete" data-order-status="delivered">
        <i class="fas fa-circle-check"></i> Mark as complete
    </button>`);

    return `<div class="account-workflow">
        <span class="account-workflow-label">Order workflow</span>
        <div class="account-workflow-btns">${buttons.join('')}</div>
    </div>`;
}

// Posts the new status and resolves with the saved order. Rejects with store-api's own
// message - notably the 409 a paid order answers a backwards move with - so callers can
// put it straight in front of the user.
async function setOrderWorkflowStatus(orderId, status) {
    const url = MY_ORDER_STATUS_URL_TEMPLATE.replace('/0/', '/' + orderId + '/');
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ status }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Could not update this order.');
    return data;
}

const AccountDrawer = {
    _loaded: false,

    open() {
        const drawer = document.getElementById('accountDrawer');
        if (!drawer) return;
        drawer.classList.add('active');
        drawer.setAttribute('aria-hidden', 'false');
        document.getElementById('accountDrawerOverlay')?.classList.add('active');
        document.body.style.overflow = 'hidden';
        if (!this._loaded) {
            this._loaded = true;
            this.loadOrders();
        }
    },

    close() {
        const drawer = document.getElementById('accountDrawer');
        if (!drawer) return;
        drawer.classList.remove('active');
        drawer.setAttribute('aria-hidden', 'true');
        document.getElementById('accountDrawerOverlay')?.classList.remove('active');
        document.body.style.overflow = '';
        // Reopening starts at the list again - coming back to a drawer still parked on
        // one old order (with no visible sign of how you got there) reads as a bug.
        this.closeOrder();
    },

    showTab(name) {
        document.querySelectorAll('.account-tab').forEach(tab => {
            const on = tab.dataset.accountTab === name;
            tab.classList.toggle('active', on);
            tab.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        document.getElementById('accountPanelOrders')?.classList.toggle('active', name === 'orders');
        document.getElementById('accountPanelSettings')?.classList.toggle('active', name === 'settings');
        // Switching tabs always leaves the per-order detail view - it belongs to the
        // Orders tab, and leaving it visible under the Settings tab would be nonsense.
        document.getElementById('accountPanelOrderDetail')?.classList.remove('active');
    },

    async loadOrders() {
        const list = document.getElementById('accountOrdersList');
        const loading = document.getElementById('accountOrdersLoading');
        if (!list) return;
        try {
            const res = await fetch(PROFILE_ORDERS_URL, { headers: { 'Accept': 'application/json' } });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Could not load your orders.');
            this.renderOrders(data);
        } catch (err) {
            list.innerHTML = `<div class="account-orders-empty">
                <i class="fas fa-triangle-exclamation"></i>${ebEscapeHtml(err.message)}
            </div>`;
            // A failed load shouldn't be permanent - let the next open try again.
            this._loaded = false;
        } finally {
            if (loading) loading.style.display = 'none';
        }
    },

    renderOrders(orders) {
        const list = document.getElementById('accountOrdersList');
        if (!orders.length) {
            list.innerHTML = `<div class="account-orders-empty">
                <i class="fas fa-receipt"></i>Nothing here yet — your orders will appear once you check out.
            </div>`;
            return;
        }
        list.innerHTML = orders.map(o => {
            const date = o.created_at
                ? new Date(o.created_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
                : '';
            const tags = [];
            const paid = o.payment_status === 'paid';
            const refunded = o.payment_status === 'refunded';
            const cancelled = o.status === 'cancelled';
            // What the row IS: a Quote until it's paid, an Invoice once it is - the same
            // single-field rule the printed document uses (see buildPrintTemplate). Only
            // an unpaid customer KHQR row is a plain "Order": it has been placed but not
            // yet settled. See Order.order_type in store-api.
            // Refunded rows keep the Invoice word for the same reason the printed
            // document does - the invoice was issued - and say so in a tag of their own.
            const docWord = (paid || refunded) ? 'Invoice' : (o.order_type === 'order' ? 'Order' : 'Quote');
            tags.push(`<span class="account-tag ${paid ? 'paid' : (o.order_type === 'order' ? 'order' : '')}">${docWord}</span>`);
            if (refunded && !cancelled) tags.push('<span class="account-tag unpaid">Refunded</span>');
            // Payment state, but never on a cancelled row: "Paid" beside "Cancelled" read
            // as a live sale that no longer exists, which is what the admin table already
            // avoids by showing cancelled rows as cancelled and nothing else. A cancelled
            // row that WAS paid is money owed back - staff see that spelled out in the
            // admin modal ("Cancelled (was paid by KHQR)"), which is where a refund is
            // actually handled.
            // "Awaiting payment" only where something is genuinely still owed - never on
            // a refunded row, which is finished and has its own tag above.
            if (!cancelled && !refunded && o.payment_status && !paid) {
                tags.push('<span class="account-tag unpaid">Awaiting payment</span>');
            }
            if (o.status) tags.push(`<span class="account-tag">${ebEscapeHtml(o.status)}</span>`);
            // A <button>, not a <div>: the whole card opens the order, so it has to be
            // focusable and Enter/Space-activatable like any other control.
            return `<button type="button" class="account-order-card" data-order-id="${o.id}">
                <div class="account-order-top">
                    <span class="account-order-no">#${ebEscapeHtml(o.order_number || o.id)}</span>
                    <span class="account-order-total">${formatPrice(o.grand_total)}</span>
                </div>
                <div class="account-order-meta">
                    ${date ? `<span><i class="fas fa-calendar"></i> ${ebEscapeHtml(date)}</span>` : ''}
                    <span>${o.item_count} item${o.item_count === 1 ? '' : 's'}</span>
                    ${o.clinic_name ? `<span>${ebEscapeHtml(o.clinic_name)}</span>` : ''}
                </div>
                <div class="account-order-tags">${tags.join('')}</div>
            </button>`;
        }).join('');
        list.querySelectorAll('.account-order-card').forEach(card => {
            card.addEventListener('click', () => this.openOrder(Number(card.dataset.orderId)));
        });
    },

    // ---- order detail ----
    // The list only carries summaries, so opening an order fetches it in full
    // (/profile/orders/<id>). Cached per page view: the same order is re-opened often
    // enough - list -> detail -> back -> detail - that refetching each time is waste,
    // and an already-placed order's data doesn't change under us.
    _orderCache: {},

    async openOrder(orderId) {
        const panel = document.getElementById('accountPanelOrderDetail');
        const body = document.getElementById('accountOrderDetail');
        if (!panel || !body) return;
        document.getElementById('accountPanelOrders')?.classList.remove('active');
        panel.classList.add('active');
        panel.scrollTop = 0;
        document.querySelector('.account-drawer-body').scrollTop = 0;

        const cached = this._orderCache[orderId];
        if (cached) {
            this.renderOrderDetail(cached);
            return;
        }
        body.innerHTML = '<div class="account-orders-loading"><i class="fas fa-spinner fa-spin"></i> Loading…</div>';
        try {
            const res = await fetch(`${PROFILE_ORDERS_URL}/${orderId}`, { headers: { 'Accept': 'application/json' } });
            const order = await res.json();
            if (!res.ok) throw new Error(order.detail || 'Could not load this order.');
            this._orderCache[orderId] = order;
            this.renderOrderDetail(order);
        } catch (err) {
            body.innerHTML = `<div class="account-orders-empty">
                <i class="fas fa-triangle-exclamation"></i>${ebEscapeHtml(err.message)}
            </div>`;
        }
    },

    // Back out of the detail view to whichever tab is actually selected - closing the
    // drawer calls this too, and the selected tab may well be Settings by then.
    closeOrder() {
        document.getElementById('accountPanelOrderDetail')?.classList.remove('active');
        const active = document.querySelector('.account-tab.active')?.dataset.accountTab || 'orders';
        this.showTab(active);
    },

    // Everything interpolated here is escaped: the item names are admin-entered
    // snapshots and the clinic/address came from a checkout form, i.e. free text.
    renderOrderDetail(order) {
        const body = document.getElementById('accountOrderDetail');
        // Same rules as buildPrintTemplate() - see the comment there, including why a
        // cancelled order is never treated as a paid document.
        const isPaidDocument = order.payment_status === 'paid' && order.status !== 'cancelled';
        const isRefunded = order.payment_status === 'refunded' && order.status !== 'cancelled';
        // Sub-Total/Discount are derived the same way the printed quote and the admin
        // modal derive them - from each line's snapshotted list_price vs the unit_price
        // actually charged - so all three always agree.
        const undiscountedSubtotal = order.items.reduce(
            (sum, item) => sum + deriveOldUnitPrice(item) * item.qty, 0
        );
        const itemDiscountTotal = printedCashDiscountTotal(order.items);
        const specialDiscountLabel = order.discount_type === 'cash'
            ? 'Special Discount (Cash)'
            : `Special Discount (${Number(order.discount_value || 0)}%)`;

        // Component lines ($0 bundle contents / freebies) print under their parent as
        // "Free" sub-rows, exactly as they do on the PDF and the admin modal.
        const rows = order.items.map(item => item.parent_item_id ? `
            <div class="account-item-row component">
                <span class="account-item-name">• ${ebEscapeHtml(item.product_name)} <span class="account-item-qty">×${item.qty}</span></span>
                <span class="account-item-amount">Free</span>
            </div>` : `
            <div class="account-item-row">
                <span class="account-item-name">
                    ${ebEscapeHtml(item.product_name)}
                    <span class="account-item-qty">×${item.qty}${item.product_code ? ` · ${ebEscapeHtml(item.product_code)}` : ''}</span>
                </span>
                <span class="account-item-amount">${formatPrice(printedItemAmount(item))}</span>
            </div>`).join('');

        body.innerHTML = `
            <div class="account-detail-head">
                <div>
                    <!-- Paid => Invoice, whatever the row started as. The list this
                         opened from (renderOrders above) and the full-page version
                         (auth/orders.html) both already read it that way; this heading
                         was the one place still going by order_type alone, so a quote
                         staff had just taken payment for still said "Quote" here while
                         its own PDF button offered an Invoice. -->
                    <strong>${(isPaidDocument || isRefunded) ? 'Invoice' : (order.order_type === 'order' ? 'Order' : 'Quote')} #${ebEscapeHtml(order.order_number)}</strong>
                    <span>${ebEscapeHtml(QuoteCart._formatQuoteDate(order.created_at))} · C. Code ${ebEscapeHtml(order.quote_code || '—')}</span>
                </div>
                <span class="account-order-total">${formatPrice(order.grand_total)}</span>
            </div>

            <div class="account-detail-row"><span>Clinic</span><strong>${ebEscapeHtml(order.clinic_name || '—')}</strong></div>
            <div class="account-detail-row"><span>Phone</span><strong>${ebEscapeHtml(order.phone || '—')}</strong></div>
            <div class="account-detail-row"><span>Address</span><strong>${ebEscapeHtml(order.address || '—')}</strong></div>
            <div class="account-detail-row"><span>Status</span><strong>${ebEscapeHtml(order.status || '—')}</strong></div>
            ${(order.payment_method || order.payment_status) ? `<div class="account-detail-row"><span>Payment</span><strong>${order.payment_method === 'khqr' ? 'KHQR' : order.payment_method === 'cash' ? 'Cash' : 'Paid at counter'}${order.payment_status ? ` · ${ebEscapeHtml(order.payment_status)}` : ''}</strong></div>` : ''}
            ${isRefunded ? `<div class="account-detail-row"><span>Refunded</span><strong>${ebEscapeHtml(order.refunded_at ? QuoteCart._formatQuoteDate(order.refunded_at) : 'yes')}${order.refund_reason ? ` · ${ebEscapeHtml(order.refund_reason)}` : ''}</strong></div>` : ''}

            <div class="account-items">${rows}</div>

            <div class="account-detail-row"><span>Sub-Total</span><strong>${formatPrice(undiscountedSubtotal)}</strong></div>
            <div class="account-detail-row"><span>Discount</span><strong>${formatPrice(itemDiscountTotal)}</strong></div>
            <div class="account-detail-row"><span>${specialDiscountLabel}</span><strong>${formatPrice(Number(order.discount_amount))}</strong></div>
            <div class="account-detail-row grand"><span>Grand Total</span><strong>${formatPrice(Number(order.grand_total))}</strong></div>

            ${order.status === 'cancelled' ? `
            <div class="account-cancelled-note">
                This order was cancelled, so there is no invoice for it.
            </div>` : `
            ${orderWorkflowHtml(order)}
            <button type="button" class="account-pdf-btn" id="accountOrderPdfBtn">
                <i class="fas fa-file-arrow-down"></i> Download ${(isPaidDocument || isRefunded) ? 'Invoice' : 'Quotation'} PDF
            </button>`}`;

        // Absent on a cancelled order: a cancelled sale has no invoice to hand over, and
        // both document builders refuse to title one that way anyway (docTitle above /
        // document_title() in store-api).
        document.getElementById('accountOrderPdfBtn')?.addEventListener('click', () => this.downloadOrderPDF(order));

        // Staff-only, and absent entirely for a customer - see orderWorkflowHtml().
        body.querySelectorAll('[data-order-status]').forEach(btn => {
            btn.addEventListener('click', () => this.setOrderStatus(order.id, btn.dataset.orderStatus, btn));
        });
    },

    // "Confirm order" / "Mark as complete" in the drawer. The order that comes back is
    // the one store-api saved, so the panel is re-rendered from it rather than from a
    // locally patched copy - which is also what keeps the cached copy honest.
    async setOrderStatus(orderId, status, btn) {
        const buttons = btn.closest('.account-workflow-btns')?.querySelectorAll('button') || [btn];
        const originalHtml = btn.innerHTML;
        buttons.forEach(b => { b.disabled = true; });
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving…';
        try {
            const order = await setOrderWorkflowStatus(orderId, status);
            this._orderCache[orderId] = order;
            this.renderOrderDetail(order);
            // The list panel is still mounted behind this one with the old status tag on
            // its card, so it has to be told too - otherwise backing out of the detail
            // shows the order still sitting at "pending".
            this.loadOrders();
            // No showToast() here, deliberately: .toast-container sits at z-index
            // 999999 and this drawer at 9999999, so a toast raised from inside it is
            // simply painted underneath. The re-render above is the confirmation - the
            // Status row and the buttons both change - and ebAlert() is used for the
            // failure path because it IS given a z-index above the drawers (see the
            // note beside it in base.css).
        } catch (err) {
            buttons.forEach(b => { b.disabled = false; });
            btn.innerHTML = originalHtml;
            await ebAlert(err.message, { tone: 'error' });
        }
    },

    // Re-generates the original document from the order that's on record - the same
    // two calls the admin Orders page's Print button makes (QuoteCart.buildPrintTemplate
    // + exportPDF in this file). Nothing is resubmitted and no PDF is stored anywhere:
    // the document is rebuilt in the browser each time it's asked for.
    async downloadOrderPDF(order) {
        const btn = document.getElementById('accountOrderPdfBtn');
        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating…';
        try {
            QuoteCart.buildPrintTemplate(order);
            await QuoteCart.exportPDF(
                order.quote_code,
                ['paid', 'refunded'].includes(order.payment_status) ? 'Invoice' : 'Quotation'
            );
        } catch (err) {
            await ebAlert('Sorry, the PDF could not be generated. Please try again.', { tone: 'error' });
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    const trigger = document.getElementById('accountDrawerBtn');
    const drawer = document.getElementById('accountDrawer');
    // Without the drawer in the page (logged out), the trigger stays an ordinary
    // link to /profile - hence the guard rather than an unconditional preventDefault.
    if (trigger && drawer) {
        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            AccountDrawer.open();
        });
    }
    document.getElementById('accountOrderBackBtn')?.addEventListener('click', () => AccountDrawer.closeOrder());
    document.getElementById('accountDrawerClose')?.addEventListener('click', () => AccountDrawer.close());
    document.getElementById('accountDrawerOverlay')?.addEventListener('click', () => AccountDrawer.close());
    document.querySelectorAll('.account-tab').forEach(tab => {
        tab.addEventListener('click', () => AccountDrawer.showTab(tab.dataset.accountTab));
    });
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape' || !drawer?.classList.contains('active')) return;
        // One step back per press: out of an open order first, then out of the drawer.
        if (document.getElementById('accountPanelOrderDetail')?.classList.contains('active')) {
            AccountDrawer.closeOrder();
        } else {
            AccountDrawer.close();
        }
    });
});
